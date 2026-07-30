"""Tests for StrainPrior — the agent that reuses what HERD already concluded.

Everything here is a variation on one question: when is it legitimate to let a
past conclusion stand in for a present investigation? Getting that wrong is not
a normal bug. A prior applies to every future claim that matches the strain, so
an error here is the only kind in HERD that gets *louder* the more the system
is used, and the only one that can carry one campus's mistake to another.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.config import get_thresholds
from app.contracts import (Claim, ClaimType, Entities, InstitutionSighting,
                           Strain, Verdict, VerdictLabel)
from app.investigate.agents.memory import StrainPrior
from app.investigate.aggregate import Aggregator
from tests.fakes import FakeStore

th = get_thresholds()
HERE = "vnrvjiet"
ELSEWHERE = "cbit"


def claim(institution: str = HERE) -> Claim:
    return Claim(id="c", report_id="r", institution_id=institution,
                 claim_type=ClaimType.PLACEMENT, text="x" * 60, text_en="x" * 60,
                 language="en", entities=Entities(), extraction_confidence=0.9,
                 extracted_at=datetime.now(timezone.utc))


def strain(sid: str = "s1", *, parent: str | None = None,
           seen: list[InstitutionSighting] | None = None) -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id=sid, parent_id=parent, first_seen=now, last_seen=now,
                  report_count=1, seen_at=seen or [])


def verdict(label: VerdictLabel, confidence: float, *, strain_id: str = "s1",
            institution: str = HERE) -> Verdict:
    return Verdict(id=f"v-{strain_id}-{institution}", strain_id=strain_id,
                   institution_id=institution, label=label, confidence=confidence,
                   posterior_false=0.9 if label is not VerdictLabel.TRUE else 0.05,
                   what_would_change_my_mind="an official confirmation")


def run(agent: StrainPrior, c: Claim, s: Strain):
    return asyncio.run(agent.run(c, s))


def agent(store: FakeStore, institution: str = HERE) -> StrainPrior:
    return StrainPrior(store, institution)


# --------------------------------------------------------------------------
# Nothing known
# --------------------------------------------------------------------------

def test_an_unseen_template_contributes_nothing():
    ev = run(agent(FakeStore()), claim(), strain())
    assert ev.status == "ok"
    assert ev.signal == "neutral"
    assert ev.strength == 0.0
    assert "not been investigated" in ev.finding


def test_a_neutral_finding_carries_no_sources():
    # The contract forbids a non-neutral finding without sources; the converse
    # matters for honesty rather than validity — citing a memory that concluded
    # nothing would put a footnote under an absence.
    ev = run(agent(FakeStore()), claim(), strain())
    assert ev.sources == []


def test_seen_before_but_unresolved_says_so_rather_than_staying_silent():
    store = FakeStore()
    s = strain(seen=[InstitutionSighting(institution_id=ELSEWHERE, report_count=4,
                                         local_verdict=None)])
    ev = run(agent(store), claim(), s)
    assert ev.signal == "neutral"
    assert ev.strength == 0.0
    assert "never resolved" in ev.finding


# --------------------------------------------------------------------------
# This institution's own history — read in full
# --------------------------------------------------------------------------

@pytest.mark.parametrize("label,expected", [
    (VerdictLabel.FALSE, "contradicts"),
    (VerdictLabel.MISLEADING, "contradicts"),
    (VerdictLabel.TRUE, "supports"),
])
def test_a_local_decisive_verdict_points_the_same_way_it_did_before(label, expected):
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(label, 0.9)))
    ev = run(agent(store), claim(), strain())
    assert ev.signal == expected
    assert ev.strength > 0


def test_local_weight_is_the_configured_weight_scaled_by_past_confidence():
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.8)))
    ev = run(agent(store), claim(), strain())
    expected = th.f("aggregation.strain_prior.same_institution") * 0.8
    assert ev.strength == pytest.approx(expected, abs=1e-4)


def test_a_shakier_past_verdict_makes_a_weaker_prior():
    # Uncertainty has to compound across reuse. If a 55%-confident verdict
    # produced the same prior as a 95%-confident one, HERD would launder a
    # hedge into a certainty the moment the claim was seen twice.
    store_low, store_high = FakeStore(), FakeStore()
    asyncio.run(store_low.save_verdict(verdict(VerdictLabel.FALSE, 0.55)))
    asyncio.run(store_high.save_verdict(verdict(VerdictLabel.FALSE, 0.95)))
    low = run(agent(store_low), claim(), strain())
    high = run(agent(store_high), claim(), strain())
    assert low.strength < high.strength


@pytest.mark.parametrize("label", [VerdictLabel.UNVERIFIED])
def test_an_abstention_is_never_inherited(label):
    # "We could not tell" is not a finding. Treating it as one is how a system
    # converts its own ignorance into evidence.
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(label, 0.9)))
    ev = run(agent(store), claim(), strain())
    assert ev.signal == "neutral"
    assert ev.strength == 0.0


def test_a_zero_confidence_verdict_is_skipped_rather_than_emitted_at_zero():
    # Emitting strength 0 with signal='contradicts' would violate the Evidence
    # contract's "a direction needs a source" rule in spirit: a direction with
    # no weight is a claim the system cannot back.
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.0)))
    ev = run(agent(store), claim(), strain())
    assert ev.signal == "neutral"


def test_the_local_source_is_a_memory_not_a_web_citation():
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.9)))
    ev = run(agent(store), claim(), strain())
    assert [s.kind for s in ev.sources] == ["memory"]
    assert ev.sources[0].url.startswith("herd://strain/")
    assert ev.correlation_group == "memory"


# --------------------------------------------------------------------------
# Other institutions — the label on the sighting, and nothing else (ADR-0026)
# --------------------------------------------------------------------------

def test_another_campus_history_is_usable_but_weaker_than_our_own():
    local, remote = FakeStore(), FakeStore()
    asyncio.run(local.save_verdict(verdict(VerdictLabel.FALSE, 1.0)))
    s_remote = strain(seen=[InstitutionSighting(institution_id=ELSEWHERE,
                                                report_count=9,
                                                local_verdict=VerdictLabel.FALSE)])
    ours = run(agent(local), claim(), strain())
    theirs = run(agent(remote), claim(), s_remote)
    assert theirs.signal == "contradicts"
    assert theirs.strength < ours.strength


def test_another_campus_verdict_record_is_never_even_read():
    # Asserting on the output is not enough. An agent that fetches the remote
    # verdict and then declines to use it has already crossed the boundary, and
    # the next refactor will keep the fetch and drop the declining.
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.TRUE, 0.99,
                                           institution=ELSEWHERE)))
    s = strain(seen=[InstitutionSighting(institution_id=ELSEWHERE, report_count=3,
                                         local_verdict=VerdictLabel.FALSE)])
    ev = run(agent(store), claim(), s)

    assert all(inst == HERE for _, inst in store.verdict_reads), store.verdict_reads
    # And the label on the sighting won, not the richer record next to it.
    assert ev.signal == "contradicts"


def test_our_own_history_outranks_another_campus_disagreement():
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.TRUE, 0.9)))
    s = strain(seen=[InstitutionSighting(institution_id=ELSEWHERE, report_count=50,
                                         local_verdict=VerdictLabel.FALSE)])
    ev = run(agent(store), claim(), s)
    assert ev.signal == "supports"
    assert "this institution" in ev.sources[0].title


def test_our_own_sighting_is_not_mistaken_for_someone_elses():
    store = FakeStore()
    s = strain(seen=[InstitutionSighting(institution_id=HERE, report_count=5,
                                         local_verdict=VerdictLabel.FALSE)])
    ev = run(agent(store), claim(), s)
    # No verdict record exists here, so a sighting bearing our own id must not
    # sneak in through the cross-institution path at cross-institution weight.
    assert ev.signal == "neutral"


def test_the_most_reported_sighting_is_the_one_that_speaks():
    store = FakeStore()
    s = strain(seen=[
        InstitutionSighting(institution_id="a", report_count=1,
                            local_verdict=VerdictLabel.TRUE),
        InstitutionSighting(institution_id="b", report_count=40,
                            local_verdict=VerdictLabel.FALSE)])
    ev = run(agent(store), claim(), s)
    assert ev.signal == "contradicts"
    assert "40 time(s)" in ev.finding


def test_a_remote_finding_says_out_loud_that_it_cannot_decide():
    # The finding text is shown to a student. If it reads like a verdict, the
    # structural guard in aggregate() is invisible to the person it protects.
    store = FakeStore()
    s = strain(seen=[InstitutionSighting(institution_id=ELSEWHERE, report_count=3,
                                         local_verdict=VerdictLabel.FALSE)])
    ev = run(agent(store), claim(), s)
    assert "cannot decide this claim on its own" in ev.finding


# --------------------------------------------------------------------------
# Lineage
# --------------------------------------------------------------------------

def test_a_mutation_inherits_its_parents_history():
    store = FakeStore()
    parent = strain("s0")
    asyncio.run(store.upsert_strain(parent))
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.9, strain_id="s0")))
    ev = run(agent(store), claim(), strain("s1", parent="s0"))
    assert ev.signal == "contradicts"
    assert "earlier version" in ev.finding


def test_the_childs_own_verdict_wins_over_its_parents():
    store = FakeStore()
    asyncio.run(store.upsert_strain(strain("s0")))
    asyncio.run(store.save_verdict(verdict(VerdictLabel.TRUE, 0.9, strain_id="s0")))
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.9, strain_id="s1")))
    ev = run(agent(store), claim(), strain("s1", parent="s0"))
    assert ev.signal == "contradicts"
    assert "earlier version" not in ev.finding


def test_a_lineage_cycle_terminates_instead_of_hanging_the_investigation():
    # A cycle is a data bug, not a user input, which is exactly why it must not
    # be able to take the whole cascade down with it.
    store = FakeStore()
    asyncio.run(store.upsert_strain(strain("s1", parent="s2")))
    asyncio.run(store.upsert_strain(strain("s2", parent="s1")))
    ev = run(agent(store), claim(), strain("s1", parent="s2"))
    assert ev.status == "ok"


def test_a_missing_ancestor_stops_the_walk_rather_than_failing():
    store = FakeStore()
    ev = run(agent(store), claim(), strain("s1", parent="ghost"))
    assert ev.status == "ok"
    assert ev.signal == "neutral"


# --------------------------------------------------------------------------
# Failure, and standing
# --------------------------------------------------------------------------

def test_a_broken_store_degrades_instead_of_raising():
    store = FakeStore()
    store.raise_on_get_verdict = RuntimeError("database is locked")
    ev = run(agent(store), claim(), strain())
    assert ev.status == "unavailable"
    assert ev.strength == 0.0
    assert ev.signal == "neutral"
    assert "database is locked" in (ev.error or "")


def test_memory_alone_cannot_produce_a_verdict_however_strong_it_is():
    # ADR-0026's guarantee, asserted end to end with this agent's real output
    # rather than a hand-built Evidence that happens to resemble it.
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 1.0)))
    ev = run(agent(store), claim(), strain())
    result = Aggregator.from_thresholds(th).aggregate([ev])
    assert result.label is VerdictLabel.UNVERIFIED
    assert result.downgraded_for_insufficient_standing


def test_memory_sharpens_a_verdict_that_other_evidence_already_supports():
    # The flip side: if the prior could never move anything, the recognition
    # layer would be expensive decoration.
    from tests.test_aggregate import ev as make_ev  # shared Evidence helper

    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.9)))
    prior = run(agent(store), claim(), strain())
    other = make_ev("DomainForensics", "contradicts", 0.6, tier=1,
                    group="identity_mismatch")

    agg = Aggregator.from_thresholds(th)
    without = agg.aggregate([other])
    with_prior = agg.aggregate([other, prior])
    assert with_prior.posterior_false > without.posterior_false


def test_it_is_cheap_enough_to_run_on_every_report():
    store = FakeStore()
    asyncio.run(store.save_verdict(verdict(VerdictLabel.FALSE, 0.9)))
    a, c, s = agent(store), claim(), strain()

    async def many():
        for _ in range(200):
            await a.run(c, s)

    import time
    started = time.perf_counter()
    asyncio.run(many())
    per_call_ms = (time.perf_counter() - started) * 1000 / 200
    assert per_call_ms < 5.0, f"{per_call_ms:.2f} ms per lookup"
