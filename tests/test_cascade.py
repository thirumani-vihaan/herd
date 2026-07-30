"""Tests for the tiered cascade (ADR-0011).

The cascade's whole value is what it *doesn't* do: tiers it never runs, money
it never spends. That makes it unusually easy to get wrong in a way that looks
fine — an over-eager exit saves money and quietly makes verdicts unreachable;
a timid one is correct and costs ten times more per report.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.config import get_thresholds
from app.contracts import (Claim, ClaimType, Entities, Evidence, Source, Strain,
                           VerdictLabel)
from app.interfaces import InvestigationAgent
from app.investigate.aggregate import Aggregator
from app.investigate.cascade import Cascade

th = get_thresholds()


def claim() -> Claim:
    return Claim(id="c", report_id="r", institution_id="i",
                 claim_type=ClaimType.PLACEMENT, text="x" * 60, text_en="x" * 60,
                 language="en", entities=Entities(),
                 extraction_confidence=0.9, extracted_at=datetime.now(timezone.utc))


def strain() -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id="s", first_seen=now, last_seen=now, report_count=1)


class Fake(InvestigationAgent):
    """A scripted agent. Records that it ran, so 'never ran' is assertable."""

    def __init__(self, name: str, tier: int, signal: str = "neutral",
                 strength: float = 0.0, *, group: str = "independent",
                 applies: bool = True, raises: bool = False,
                 delay: float = 0.0, status: str = "ok") -> None:
        self.name, self.tier = name, tier
        self.signal, self.strength, self.group = signal, strength, group
        self._applies, self.raises, self.delay, self.status = applies, raises, delay, status
        self.ran = False

    def applies_to(self, c: Claim) -> bool:
        return self._applies

    async def run(self, c: Claim, s: Strain) -> Evidence:
        self.ran = True
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise RuntimeError("agent exploded")
        sources = [] if self.signal == "neutral" else [
            Source(url=f"herd://test/{self.name}", title="t", excerpt="t",
                   retrieved_at=datetime.now(timezone.utc), kind="rule")]
        return Evidence(agent=self.name, institution_id=c.institution_id,
                        tier=self.tier, status=self.status, signal=self.signal,
                        strength=self.strength if self.status == "ok" else 0.0,
                        finding="t", sources=sources,
                        correlation_group=self.group, elapsed_ms=1)


def build(agents, *, deadline_ms: int = 20000) -> Cascade:
    return Cascade(
        agents, Aggregator.from_thresholds(th),
        exit_bars={0: th.f("cascade.exit.tier0"), 1: th.f("cascade.exit.tier1"),
                   2: th.f("cascade.exit.tier2")},
        false_exit_multiplier=th.f("cascade.false_exit_multiplier"),
        unverified_exit_multiplier=th.f("cascade.unverified_exit_multiplier"),
        deadline_ms=deadline_ms,
        confirming_agents=set(th.get("verdict.confirming_agents")))


def run(cascade: Cascade):
    return asyncio.run(cascade.run(claim(), strain()))


# --------------------------------------------------------------------------
# the point of the cascade: not spending money
# --------------------------------------------------------------------------

def test_conclusive_tier0_never_reaches_paid_tiers():
    """The cost story. If this stops holding, HERD is a normal fact-checker
    with extra steps."""
    t0 = Fake("FraudHeuristics", 0, "contradicts", 1.0, group="a")
    t0b = Fake("TemplateProvenance", 0, "contradicts", 1.0, group="b")
    t1 = Fake("URLSafety", 1, "contradicts", 0.5)
    t2 = Fake("InstitutionalSource", 2, "supports", 0.5)
    t3 = Fake("OpenWebResearch", 3, "contradicts", 0.5)
    result = run(build([t0, t0b, t1, t2, t3]))

    assert result.aggregation.label is VerdictLabel.FALSE
    assert result.highest_tier_reached == 0
    assert not t1.ran and not t2.ran and not t3.ran
    assert result.trace[0].exited


def test_inconclusive_tier0_falls_through():
    weak = Fake("FraudHeuristics", 0, "contradicts", 0.2)
    t1 = Fake("URLSafety", 1, "contradicts", 0.2)
    result = run(build([weak, t1]))
    assert t1.ran
    assert result.highest_tier_reached == 1


def test_tiers_run_in_order():
    order: list[int] = []

    class Recorder(Fake):
        async def run(self, c, s):
            order.append(self.tier)
            return await super().run(c, s)

    run(build([Recorder("c", 2, "contradicts", 0.1), Recorder("a", 0, "contradicts", 0.1),
               Recorder("b", 1, "contradicts", 0.1)]))
    assert order == sorted(order)


def test_agents_within_a_tier_run_concurrently():
    """Sequential agents inside a tier would turn three 1-second lookups into
    three seconds, which is the entire latency budget for one report."""
    slow = [Fake(f"a{i}", 1, delay=0.25) for i in range(4)]
    import time
    started = time.perf_counter()
    run(build(slow + [Fake("z", 0)]))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.7, f"tier took {elapsed:.2f}s; agents are running in series"


# --------------------------------------------------------------------------
# exiting is asymmetric, and must not make a verdict unreachable
# --------------------------------------------------------------------------

def test_exiting_toward_false_is_harder_than_exiting_away_from_it(th_=th):
    assert (th_.f("cascade.false_exit_multiplier")
            > th_.f("cascade.unverified_exit_multiplier"))


def test_does_not_exit_early_while_confirmation_is_still_possible():
    """The interaction that would have made TRUE unreachable in production.

    Tier 0 sees nothing wrong, the posterior drops, and the naive rule exits —
    returning UNVERIFIED for a notice that the very next tier would have
    confirmed. The config would still say TRUE was reachable."""
    reassuring = Fake("FraudHeuristics", 0, "supports", 1.0, group="a")
    confirmer = Fake("InstitutionalSource", 2, "supports", 1.0, group="b")
    result = run(build([reassuring, confirmer]))

    assert confirmer.ran, "cascade exited before the only agent that can confirm"
    assert result.aggregation.label is VerdictLabel.TRUE


def test_does_exit_early_once_confirmation_has_been_obtained():
    """Having got the confirmation, there is nothing left to buy."""
    confirmer = Fake("InstitutionalSource", 2, "supports", 1.0, group="b")
    expensive = Fake("OpenWebResearch", 3, "contradicts", 1.0, group="c")
    result = run(build([Fake("FraudHeuristics", 0, "supports", 1.0, group="a"),
                        confirmer, expensive]))
    assert confirmer.ran
    assert not expensive.ran
    assert result.aggregation.label is VerdictLabel.TRUE


def test_still_exits_early_toward_false_even_though_confirmers_remain():
    """The guard is one-directional. A claim heading toward FALSE has no
    reason to wait for an agent whose job is to confirm it."""
    damning = Fake("FraudHeuristics", 0, "contradicts", 1.0, group="a")
    damning2 = Fake("TemplateProvenance", 0, "contradicts", 1.0, group="b")
    confirmer = Fake("InstitutionalSource", 2, "supports", 1.0)
    run(build([damning, damning2, confirmer]))
    assert not confirmer.ran


# --------------------------------------------------------------------------
# resilience: rule 3 enforced from outside the agent
# --------------------------------------------------------------------------

def test_a_raising_agent_does_not_stop_the_investigation():
    """Agents are required not to raise. They are also written by people."""
    boom = Fake("DomainForensics", 1, raises=True)
    other = Fake("URLSafety", 1, "contradicts", 0.5)
    result = run(build([Fake("FraudHeuristics", 0), boom, other]))

    degraded = [e for e in result.evidence if e.agent == "DomainForensics"]
    assert degraded and degraded[0].status == "unavailable"
    assert degraded[0].strength == 0.0
    assert degraded[0].error
    assert any(e.agent == "URLSafety" and e.status == "ok" for e in result.evidence)


def test_a_hanging_agent_cannot_hold_the_deadline():
    hang = Fake("OpenWebResearch", 1, delay=5.0)
    result = run(build([Fake("FraudHeuristics", 0), hang], deadline_ms=300))
    assert result.elapsed_ms < 2000
    assert any(e.agent == "OpenWebResearch" and e.status == "unavailable"
               for e in result.evidence)


def test_an_agent_whose_applicability_check_throws_is_skipped():
    class Broken(Fake):
        def applies_to(self, c):
            raise RuntimeError("cannot decide")

    broken = Broken("ContactForensics", 1)
    run(build([Fake("FraudHeuristics", 0), broken]))
    assert not broken.ran


def test_not_applicable_agents_cost_nothing():
    skipped = Fake("ContactForensics", 1, "contradicts", 1.0, applies=False)
    result = run(build([Fake("FraudHeuristics", 0), skipped]))
    assert not skipped.ran
    assert "ContactForensics" in result.trace[1].agents_skipped
    assert not any(e.agent == "ContactForensics" for e in result.evidence)


def test_cascade_with_no_agents_returns_the_prior():
    result = run(build([]))
    assert result.evidence == []
    assert result.aggregation.posterior_false == pytest.approx(
        th.f("aggregation.prior_false"), abs=1e-6)
    assert result.aggregation.label is VerdictLabel.UNVERIFIED


def test_deadline_stops_further_tiers():
    result = run(build([Fake("a", 0, delay=0.4), Fake("b", 1), Fake("c", 2)],
                       deadline_ms=200))
    assert result.deadline_exceeded
    assert result.highest_tier_reached < 2


# --------------------------------------------------------------------------
# the trace is what the demo shows, so it has to be true
# --------------------------------------------------------------------------

def test_trace_records_what_each_tier_cost_and_bought():
    result = run(build([Fake("FraudHeuristics", 0, "contradicts", 0.2),
                        Fake("URLSafety", 1, "contradicts", 0.2)]))
    assert [t.tier for t in result.trace] == [0, 1]
    for t in result.trace:
        assert t.agents_run
        assert 0.0 <= t.posterior_after <= 1.0
        assert t.elapsed_ms >= 0
    assert result.trace[-1].label_after == result.aggregation.label.value


def test_exit_reason_is_recorded_when_the_cascade_stops_early():
    result = run(build([Fake("FraudHeuristics", 0, "contradicts", 1.0, group="a"),
                        Fake("TemplateProvenance", 0, "contradicts", 1.0, group="b"),
                        Fake("URLSafety", 1)]))
    assert result.trace[0].exited
    assert "cleared the tier-0 bar" in result.trace[0].exit_reason


def test_tiers_skipped_is_reported_honestly():
    result = run(build([Fake("FraudHeuristics", 0, "contradicts", 1.0, group="a"),
                        Fake("TemplateProvenance", 0, "contradicts", 1.0, group="b"),
                        Fake("URLSafety", 1), Fake("InstitutionalSource", 2),
                        Fake("OpenWebResearch", 3)]))
    assert result.tiers_skipped == 3


def test_no_thresholds_hardcoded_in_the_cascade():
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "investigate"
           / "cascade.py").read_text(encoding="utf-8")
    allowed = {0.0, 1.0, 0.5, 1000.0}  # midpoint of a probability, and ms->s
    found = {n.value for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert not (found - allowed), f"hardcoded thresholds in cascade.py: {found - allowed}"
