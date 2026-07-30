"""Tests for evidence aggregation and the Tier-0 agents.

The asymmetries in config/thresholds.yaml are claims about how the world works
— "colleges announce late, so absence is weak evidence" — and a claim about the
world that nothing can falsify is decoration. Each one gets a test here that
fails if someone quietly makes the system symmetric again.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import get_thresholds
from app.contracts import Evidence, ForwardMarkers, Source, Strain, VerdictLabel
from app.investigate.aggregate import Aggregator, explain
from app.investigate.agents import FraudHeuristics, TemplateProvenance, load_rules
from app.perceive.extract import deterministic_extract
from app.perceive.redact import redact_text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def th():
    return get_thresholds()


@pytest.fixture(scope="module")
def agg(th):
    return Aggregator.from_thresholds(th)


def ev(agent: str, signal: str, strength: float, *, group: str = "independent",
       status: str = "ok", tier: int = 0) -> Evidence:
    # The contract refuses a non-neutral finding with no sources, and it is
    # right to: an agent that concludes without citing anything is the thing
    # this design exists to prevent. So test evidence cites something too.
    sources = [] if signal == "neutral" else [
        Source(url=f"herd://test/{agent}", title="test source", excerpt="t",
               retrieved_at=datetime.now(timezone.utc), kind="rule")]
    # The contract also refuses a non-ok agent that claims to have learned
    # something. A crashed agent knows nothing, so it weighs nothing.
    return Evidence(agent=agent, institution_id="i", tier=tier, status=status,
                    signal=signal, strength=strength if status == "ok" else 0.0,
                    finding="t", sources=sources,
                    correlation_group=group, elapsed_ms=1)


def strain(report_count: int = 1) -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id="s", first_seen=now, last_seen=now, report_count=report_count)


def claim_from(text: str, ctype_hint: str = ""):
    red, _ = redact_text(text)
    return deterministic_extract(red, report_id="r", institution_id="i", claim_id="c")


# --------------------------------------------------------------------------
# the encoded asymmetries
# --------------------------------------------------------------------------

def test_neutral_evidence_contributes_exactly_zero(agg):
    """A safe-browsing lookup that returns no hit has not exonerated anything.

    It is the single easiest place to accidentally build in a bias toward
    TRUE, because "no hit" feels like good news. It is not news at all.
    """
    base = agg.aggregate([])
    with_neutral = agg.aggregate([ev("URLSafety", "neutral", 0.9)])
    assert with_neutral.log_odds == pytest.approx(base.log_odds)
    assert with_neutral.contributions == []


def test_unavailable_agent_contributes_nothing(agg):
    a = agg.aggregate([ev("OpenWebResearch", "contradicts", 0.9, status="unavailable")])
    assert a.contributions == []
    assert a.posterior_false == pytest.approx(agg.aggregate([]).posterior_false)


def test_institutional_absence_is_capped_but_presence_is_not(agg, th):
    cap = th.f("aggregation.caps.InstitutionalSource.contradicts")
    against = agg.aggregate([ev("InstitutionalSource", "contradicts", 1.0)])
    assert against.contributions[0].cap_applied == cap
    assert abs(against.contributions[0].delta_log_odds) == pytest.approx(
        cap * th.f("aggregation.reliability.InstitutionalSource") * agg.scale, rel=1e-3)

    for_ = agg.aggregate([ev("InstitutionalSource", "supports", 1.0)])
    assert abs(for_.contributions[0].delta_log_odds) > abs(
        against.contributions[0].delta_log_odds)


def test_official_channel_absence_weighs_more_than_institutional_absence(agg, th):
    """A careers page is a more complete record than a college website, so its
    silence means more. If these two ever become equal, the ordering that
    justified having both agents has been lost."""
    assert (th.f("aggregation.caps.OfficialChannel.contradicts")
            > th.f("aggregation.caps.InstitutionalSource.contradicts"))


def test_strain_prior_alone_can_never_reach_a_verdict(agg, th):
    """ADR-0026. Seeing the same template at another college shortens the
    investigation; it must never BE the investigation, or one institution's
    mistake becomes every institution's verdict."""
    for signal in ("contradicts", "supports"):
        a = agg.aggregate([ev("StrainPrior", signal, 1.0)])
        assert a.label is VerdictLabel.UNVERIFIED, (
            f"StrainPrior alone reached {a.label} at p={a.posterior_false:.3f}")
        assert a.downgraded_for_insufficient_standing


def test_strain_prior_still_counts_alongside_local_evidence(agg):
    """It may not conclude alone, but it must still matter — otherwise the
    cross-institution memory is decorative."""
    without = agg.aggregate([ev("FraudHeuristics", "contradicts", 0.4, group="a")])
    with_prior = agg.aggregate([
        ev("FraudHeuristics", "contradicts", 0.4, group="a"),
        ev("StrainPrior", "contradicts", 0.9, group="b"),
    ])
    assert with_prior.posterior_false > without.posterior_false
    assert not with_prior.downgraded_for_insufficient_standing


def test_correlated_signals_are_discounted(agg, th):
    """Three faces of one attack kit are not three discoveries."""
    independent = agg.aggregate([
        ev("DomainForensics", "contradicts", 0.6, group="link_obfuscation"),
        ev("ContactForensics", "contradicts", 0.6, group="identity_mismatch"),
    ])
    correlated = agg.aggregate([
        ev("DomainForensics", "contradicts", 0.6, group="link_obfuscation"),
        ev("ContactForensics", "contradicts", 0.6, group="link_obfuscation"),
    ])
    assert correlated.posterior_false < independent.posterior_false
    assert any(c.discounted for c in correlated.contributions)
    assert not any(c.discounted for c in independent.contributions)


def test_independent_sentinel_never_discounts_itself(agg):
    """'independent' is the absence of a group, not a group. Two unrelated
    agents both defaulting to it must not silence each other."""
    a = agg.aggregate([
        ev("DomainForensics", "contradicts", 0.5),
        ev("ContactForensics", "contradicts", 0.5),
    ])
    assert not any(c.discounted for c in a.contributions)


def test_posterior_never_saturates(agg, th):
    """Ten agents screaming must still leave room for doubt. A system that can
    say 'certain' will eventually say it about something it got wrong."""
    a = agg.aggregate([ev(f"A{i}", "contradicts", 1.0, group=f"g{i}") for i in range(10)])
    assert a.clamped
    assert a.log_odds == pytest.approx(th.f("aggregation.max_abs_log_odds"))
    assert a.posterior_false < 0.999
    assert a.confidence <= 1.0


def test_clamp_is_symmetric(agg, th):
    a = agg.aggregate([ev(f"A{i}", "supports", 1.0, group=f"g{i}") for i in range(10)])
    assert a.log_odds == pytest.approx(-th.f("aggregation.max_abs_log_odds"))


# --------------------------------------------------------------------------
# TRUE is not reachable by arithmetic alone (ADR-0028)
# --------------------------------------------------------------------------

def test_true_requires_a_confirming_source(agg):
    """The whole point. Absence of fraud indicators is not evidence of
    authenticity — it is equally consistent with a well-made scam."""
    heuristics_only = agg.aggregate([ev("FraudHeuristics", "supports", 1.0)])
    assert heuristics_only.posterior_false <= agg.bands["unverified_above"], (
        "precondition: the arithmetic should be in TRUE territory here")
    assert heuristics_only.label is VerdictLabel.UNVERIFIED
    assert heuristics_only.downgraded_for_lack_of_confirmation


def test_a_confirming_source_unlocks_true(agg):
    a = agg.aggregate([
        ev("FraudHeuristics", "supports", 0.5),
        ev("InstitutionalSource", "supports", 1.0),
    ])
    assert a.label is VerdictLabel.TRUE
    assert not a.downgraded_for_lack_of_confirmation


def test_confirming_source_that_found_nothing_does_not_unlock_true(agg):
    """`status=ok, signal=contradicts` means it looked and did not find it.
    That is the opposite of confirmation and must not be mistaken for it."""
    a = agg.aggregate([
        ev("FraudHeuristics", "supports", 1.0),
        ev("InstitutionalSource", "contradicts", 0.1),
    ])
    assert a.label is VerdictLabel.UNVERIFIED


def test_unavailable_confirming_source_does_not_unlock_true(agg):
    """A crashed agent must not be able to confirm a claim by being broken."""
    a = agg.aggregate([
        ev("FraudHeuristics", "supports", 1.0),
        ev("InstitutionalSource", "supports", 1.0, status="unavailable"),
    ])
    assert a.label is VerdictLabel.UNVERIFIED


# --------------------------------------------------------------------------
# bands, confidence, decisiveness
# --------------------------------------------------------------------------

def test_no_single_agent_can_exhaust_the_confidence_budget(th):
    """If one agent at full strength could reach the ±clamp on its own, every
    other agent's evidence would be arithmetically discarded and the cascade,
    the correlation groups and the caps would all be decoration. This is the
    weakest statement of "multi-agent" that is still true, and it is checked
    against the shipped config, not against the calibrator's memory of it."""
    scale = th.f("aggregation.log_odds_per_unit_strength")
    clamp = th.f("aggregation.max_abs_log_odds")
    assert scale * 2 <= clamp, (
        f"one agent at strength 1.0 contributes {scale}, and the clamp is "
        f"{clamp}; a single agent can decide everything")


def test_every_agent_has_a_declared_reliability(th):
    """An agent missing from the reliability table silently defaults to 1.0 —
    perfectly trustworthy — which is the wrong default for a new agent."""
    declared = set(th.get("aggregation.reliability"))
    for name in ("FraudHeuristics", "TemplateProvenance"):
        assert name in declared


def test_calibrated_constants_are_not_literals_in_code():
    """Every threshold lives in config. A literal in code is a threshold that
    recalibration will silently miss.

    Uses the AST rather than a regex so that prose in docstrings — which is
    where these numbers SHOULD appear, explained — is not mistaken for a
    hardcoded threshold."""
    import ast
    src = (ROOT / "app" / "investigate" / "aggregate.py").read_text(encoding="utf-8")
    # Neutral arithmetic, not thresholds: identity elements, halves, and the
    # epsilon that keeps logit() finite.
    allowed = {0.0, 1.0, 0.5, 2.0, 1e-6}
    found = {n.value for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert not (found - allowed), f"hardcoded thresholds in aggregate.py: {found - allowed}"


def test_no_thresholds_hardcoded_in_tier0_agents():
    """Provenance strengths are declared in the agent because they describe
    what a forwarding marker MEANS. Everything about how the system weighs
    that meaning must be injected."""
    import ast
    src = (ROOT / "app" / "investigate" / "agents" / "tier0.py").read_text(encoding="utf-8")
    allowed = {0.0, 1.0, 0.15, 0.08, 1e-9}
    found = {n.value for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert not (found - allowed), f"unexpected literals in tier0.py: {found - allowed}"


def test_bands_are_ordered(th):
    b = th.get("verdict.bands")
    assert 0 < b["unverified_above"] < b["misleading_above"] < b["false_above"] < 1


def test_confidence_is_distance_into_band_not_posterior(agg, th):
    """A claim at the very edge of MISLEADING is almost undecided. Reporting
    its posterior as confidence would announce 66% certainty about a coin
    flip between two labels."""
    edge = th.f("verdict.bands.misleading_above") + 1e-4
    deep = (th.f("verdict.bands.misleading_above") + th.f("verdict.bands.false_above")) / 2
    assert agg._confidence(edge, VerdictLabel.MISLEADING) == pytest.approx(0.5, abs=0.01)
    assert agg._confidence(deep, VerdictLabel.MISLEADING) > 0.7


def test_confidence_is_always_a_probability(agg):
    for p in [0.0, 0.01, 0.2, 0.5, 0.65, 0.9, 0.999, 1.0]:
        for label in VerdictLabel:
            if label is VerdictLabel.OUT_OF_SCOPE:
                continue
            c = agg._confidence(p, label)
            assert 0.0 <= c <= 1.0, f"{label} at p={p} gave confidence {c}"


def test_decisiveness_peaks_mid_band_and_bottoms_at_edges(agg, th):
    from app.investigate.aggregate import Aggregation
    def at(p):
        return agg.decisiveness(Aggregation(prior=0.35, posterior_false=p, log_odds=0.0,
                                            label=agg.label_for(p), confidence=0.5))
    b = th.get("verdict.bands")
    mid = (b["misleading_above"] + b["false_above"]) / 2
    assert at(mid) > at(b["misleading_above"] + 1e-4)
    assert at(b["misleading_above"]) == pytest.approx(0.0, abs=1e-6)


def test_explain_mentions_caps_and_discounts(agg):
    a = agg.aggregate([
        ev("InstitutionalSource", "contradicts", 1.0, group="absence"),
        ev("OfficialChannel", "contradicts", 1.0, group="absence"),
    ])
    lines = explain(a.contributions)
    assert any("capped" in l for l in lines)
    assert any("discounted" in l for l in lines)


# --------------------------------------------------------------------------
# Tier-0 agents
# --------------------------------------------------------------------------

SCAM = ("*Zentara Systems OFF-CAMPUS DRIVE 2026*\n\nEligible: all branches\n"
        "Limited slots! Register now:\nbit.ly/zentara-drive26\n\n"
        "Registration fee Rs.750 (mandatory)\nUPI: zentarahr@okaxis\n"
        "Last date: TOMORROW 5 PM")
GENUINE = ("Training & Placement Cell notice: pre-placement talk by Cognizant on "
           "Monday 10 AM in the seminar hall. Details on "
           "https://example-college.invalid/placements . No registration fee.")


def test_fraud_heuristics_fires_on_the_flagship_scam():
    c = claim_from(SCAM)
    fired = {r["id"] for r in FraudHeuristics()._fire(c)}
    assert "upfront_fee_for_job" in fired
    assert "personal_upi_vpa" in fired
    assert "url_shortener_on_official_link" in fired


def test_fraud_heuristics_nets_both_directions():
    """A rule engine that reports only the louder half of what it found is not
    reporting what it found."""
    fh = FraudHeuristics(official_domains={"example-college.invalid"})
    c = claim_from(GENUINE)
    fired = {r["id"] for r in fh._fire(c)}
    assert "official_domain_link" in fired
    result = asyncio.run(fh.run(c, strain()))
    assert result.signal == "supports"


def test_fraud_heuristics_cites_every_rule_including_losing_side():
    fh = FraudHeuristics(official_domains={"example-college.invalid"})
    c = claim_from(GENUINE)
    result = asyncio.run(fh.run(c, strain()))
    cited = {s.url.rsplit("/", 1)[-1] for s in result.sources}
    assert cited == {r["id"] for r in fh._fire(c)}


def test_fraud_heuristics_group_discount_matches_aggregator(th):
    """Two rules in one group must not add up like two discoveries."""
    d = th.f("aggregation.correlated_discount")
    fh = FraudHeuristics(correlated_discount=d, saturation=1.0)
    same_group = [{"id": "a", "signal": "contradicts", "strength": 0.6, "correlation_group": "g"},
                  {"id": "b", "signal": "contradicts", "strength": 0.6, "correlation_group": "g"}]
    diff_group = [{"id": "a", "signal": "contradicts", "strength": 0.6, "correlation_group": "g"},
                  {"id": "b", "signal": "contradicts", "strength": 0.6, "correlation_group": "h"}]
    assert fh._accumulate(same_group, "contradicts")[0] == pytest.approx(0.6 + d * 0.6)
    assert fh._accumulate(diff_group, "contradicts")[0] == pytest.approx(1.2)


def test_agents_never_raise():
    """Contract rule 3: an agent that raises takes the whole investigation with
    it. A broken agent must degrade to `unavailable`, not to an outage."""
    broken = FraudHeuristics(rules={"x": {"bad": "shape"}})
    broken._fire = lambda claim: (_ for _ in ()).throw(RuntimeError("boom"))
    result = asyncio.run(broken.run(claim_from(SCAM), strain()))
    assert result.status == "unavailable"
    assert result.signal == "neutral"
    assert result.strength == 0.0
    assert result.error


def test_agents_report_integer_latency():
    r = asyncio.run(FraudHeuristics().run(claim_from(SCAM), strain()))
    assert isinstance(r.elapsed_ms, int)


def test_template_provenance_is_weak_and_only_ever_contradicts():
    """Genuine notices get forwarded too. Treating reach as falsity would be
    exactly the reasoning error this system exists to correct."""
    heavy = asyncio.run(TemplateProvenance(
        ForwardMarkers(is_forwarded=True, is_frequently_forwarded=True)
    ).run(claim_from(SCAM), strain()))
    assert heavy.signal == "contradicts"
    assert heavy.strength <= 0.25

    plain = asyncio.run(TemplateProvenance(
        ForwardMarkers(is_forwarded=True)
    ).run(claim_from(GENUINE), strain(report_count=1)))
    assert plain.signal == "neutral"


def test_template_provenance_without_markers_is_neutral():
    r = asyncio.run(TemplateProvenance(None).run(claim_from(GENUINE), strain()))
    assert r.signal == "neutral"
    assert r.sources == []


def test_no_institutional_string_in_rules():
    """The portability claim: swapping HERD_INSTITUTION must require zero code
    or rule changes."""
    blob = json.dumps(load_rules()).lower()
    for banned in ("vnr", "vjiet", "hyderabad"):
        assert banned not in blob


# --------------------------------------------------------------------------
# corpus level: the two properties the demo actually rests on
# --------------------------------------------------------------------------

def _tier0_labels():
    rows = [json.loads(l) for l in
            (ROOT / "fixtures" / "labels.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    th = get_thresholds()
    cfg = th.get("aggregation")
    aggregator = Aggregator.from_thresholds(th)
    out = []
    for row in rows:
        c = claim_from(row["text"])
        agents = [
            FraudHeuristics(
                official_domains={row["institution_domain"]} if row.get("institution_domain") else set(),
                correlated_discount=cfg["correlated_discount"],
                saturation=cfg["agent_saturation"]),
            TemplateProvenance(ForwardMarkers(
                is_forwarded=row.get("forwarded"),
                is_frequently_forwarded=row.get("frequently_forwarded"))),
        ]
        evidence = [asyncio.run(a.run(c, strain())) for a in agents if a.applies_to(c)]
        out.append((row, aggregator.aggregate(evidence)))
    return out


@pytest.fixture(scope="module")
def corpus():
    return _tier0_labels()


def test_tier0_never_accuses_a_genuine_notice(corpus):
    """The one failure mode that ends the product. Everything else is a
    slower answer; this one is a libelled placement cell."""
    libelled = [r["id"] for r, a in corpus
                if r["truth"] == "TRUE"
                and a.label in (VerdictLabel.FALSE, VerdictLabel.MISLEADING)]
    assert libelled == []


def test_tier0_never_confirms_without_a_source(corpus):
    assert [r["id"] for r, a in corpus if a.label is VerdictLabel.TRUE] == []


def test_tier0_alone_catches_the_scams(corpus):
    """The offline demo claim: unplug the network and the scam is still caught."""
    scams = [(r, a) for r, a in corpus if r["truth"] in ("FALSE", "MISLEADING")]
    caught = [r["id"] for r, a in scams
              if a.label in (VerdictLabel.FALSE, VerdictLabel.MISLEADING)]
    assert len(caught) / len(scams) >= 0.60, f"only caught {len(caught)}/{len(scams)}"


def test_tier0_is_fast_enough_to_be_free():
    """Tier 0 exists so the median report costs nothing and answers instantly.
    If it ever stops being milliseconds, the tier structure has no point."""
    import time
    c = claim_from(SCAM)
    fh, tp = FraudHeuristics(), TemplateProvenance(ForwardMarkers(is_forwarded=True))
    s = strain()
    started = time.perf_counter()
    for _ in range(50):
        asyncio.run(fh.run(c, s))
        asyncio.run(tp.run(c, s))
    per_claim_ms = (time.perf_counter() - started) * 1000 / 50
    assert per_claim_ms < 30, f"tier 0 took {per_claim_ms:.1f} ms per claim"
