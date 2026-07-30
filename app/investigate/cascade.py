"""The tiered investigation cascade (ADR-0011).

Agents are not broadcast in parallel and then reconciled. They run in tiers,
cheapest first, and the cascade stops at the first tier that can settle the
question. The median report therefore costs nothing at all, and the ones that
cost money are the ones that earned it.

    tier 0   FraudHeuristics, TemplateProvenance, StrainPrior   free, ~ms
    tier 1   DomainForensics, URLSafety, ContactForensics       free tier, 1-3 s
    tier 2   InstitutionalSource, OfficialChannel               local index, 2-4 s
    tier 3   OpenWebResearch                                    LLM, 3-5 s

Three properties are load-bearing, and each one is a thing that goes wrong if
it is left implicit:

EXITING IS ASYMMETRIC. Stopping early because a claim looks false is a decision
to accuse someone on partial evidence. Stopping early because it looks fine is
a decision to stop spending. Those are not the same decision and they do not
get the same bar.

EXITING EARLY MUST NOT MAKE A VERDICT UNREACHABLE. Only Tier 2 contains agents
entitled to confirm a claim (ADR-0028). A cascade that exits at Tier 0 whenever
the arithmetic looks reassuring would never reach them, and TRUE would be
unreachable in practice while appearing perfectly reachable in the config. The
cascade therefore refuses to exit on the reassuring side while a confirming
agent it has not yet run could still change the label.

A DEADLINE IS NOT A TIMEOUT. Agents get the time that is left, not a fixed
slice, so a slow Tier 1 does not silently spend Tier 2's budget and leave the
user with a spinner.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.contracts import Claim, Evidence, Strain
from app.interfaces import InvestigationAgent
from app.investigate.aggregate import Aggregation, Aggregator


@dataclass
class TierTrace:
    """What one tier cost and what it bought — the data the demo shows."""

    tier: int
    agents_run: list[str]
    agents_skipped: list[str]
    evidence: list[Evidence]
    elapsed_ms: int
    posterior_after: float
    label_after: str
    exited: bool
    exit_reason: str = ""


@dataclass
class CascadeResult:
    aggregation: Aggregation
    evidence: list[Evidence]
    trace: list[TierTrace] = field(default_factory=list)
    elapsed_ms: int = 0
    deadline_exceeded: bool = False

    @property
    def highest_tier_reached(self) -> int:
        return max((t.tier for t in self.trace), default=-1)

    @property
    def tiers_skipped(self) -> int:
        """The headline cost number: tiers the cascade did not have to buy."""
        return max(0, 3 - self.highest_tier_reached)


class Cascade:
    def __init__(self, agents: list[InvestigationAgent], aggregator: Aggregator,
                 *, exit_bars: dict[int, float], false_exit_multiplier: float,
                 unverified_exit_multiplier: float, deadline_ms: int,
                 confirming_agents: set[str]) -> None:
        self.aggregator = aggregator
        self.exit_bars = exit_bars
        self.false_exit_multiplier = false_exit_multiplier
        self.unverified_exit_multiplier = unverified_exit_multiplier
        self.deadline_ms = deadline_ms
        self.confirming_agents = confirming_agents
        self.tiers: dict[int, list[InvestigationAgent]] = {}
        for a in agents:
            self.tiers.setdefault(a.tier, []).append(a)

    async def run(self, claim: Claim, strain: Strain) -> CascadeResult:
        started = time.perf_counter()
        evidence: list[Evidence] = []
        trace: list[TierTrace] = []
        deadline_exceeded = False

        for tier in sorted(self.tiers):
            remaining_ms = self.deadline_ms - (time.perf_counter() - started) * 1000
            if remaining_ms <= 0:
                deadline_exceeded = True
                break

            tier_started = time.perf_counter()
            applicable, skipped = [], []
            for agent in self.tiers[tier]:
                (applicable if self._applies(agent, claim) else skipped).append(agent)

            if applicable:
                new_evidence = await self._run_tier(applicable, claim, strain,
                                                    remaining_ms / 1000.0)
                evidence.extend(new_evidence)
            else:
                new_evidence = []

            aggregation = self.aggregator.aggregate(evidence)
            exit_now, reason = self._should_exit(tier, aggregation, evidence)

            trace.append(TierTrace(
                tier=tier,
                agents_run=[a.name for a in applicable],
                agents_skipped=[a.name for a in skipped],
                evidence=new_evidence,
                elapsed_ms=int(round((time.perf_counter() - tier_started) * 1000)),
                posterior_after=round(aggregation.posterior_false, 4),
                label_after=aggregation.label.value,
                exited=exit_now, exit_reason=reason))

            if exit_now:
                break

        return CascadeResult(
            aggregation=self.aggregator.aggregate(evidence),
            evidence=evidence, trace=trace,
            elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
            deadline_exceeded=deadline_exceeded)

    # -- tier execution ----------------------------------------------------

    def _applies(self, agent: InvestigationAgent, claim: Claim) -> bool:
        """Rule 4 of the agent contract, defensively.

        An agent whose applicability check throws is an agent that has just
        told us it cannot handle this claim.
        """
        try:
            return bool(agent.applies_to(claim))
        except Exception:
            return False

    async def _run_tier(self, agents: list[InvestigationAgent], claim: Claim,
                        strain: Strain, budget_s: float) -> list[Evidence]:
        results = await asyncio.gather(
            *(self._run_one(a, claim, strain, budget_s) for a in agents),
            return_exceptions=False)
        return [r for r in results if r is not None]

    async def _run_one(self, agent: InvestigationAgent, claim: Claim,
                       strain: Strain, budget_s: float) -> Evidence | None:
        """Rule 3 of the agent contract, enforced from the outside.

        Agents are required not to raise. They are also written by people, so
        the cascade does not depend on their good behaviour: a raising or
        hanging agent becomes `unavailable` evidence, and the investigation
        continues without it. A cascade that can be taken down by one bad
        agent has no business calling itself resilient.
        """
        started = time.perf_counter()
        try:
            return await asyncio.wait_for(agent.run(claim, strain), timeout=budget_s)
        except asyncio.TimeoutError:
            return self._degraded(agent, claim, started, "timed out")
        except Exception as exc:
            return self._degraded(agent, claim, started, str(exc)[:200])

    def _degraded(self, agent: InvestigationAgent, claim: Claim,
                  started: float, error: str) -> Evidence:
        return Evidence(
            agent=getattr(agent, "name", type(agent).__name__),
            institution_id=claim.institution_id,
            tier=getattr(agent, "tier", 0), status="unavailable", signal="neutral",
            strength=0.0, finding="agent did not complete", sources=[],
            correlation_group="independent",
            elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
            error=error)

    # -- when to stop ------------------------------------------------------

    def _should_exit(self, tier: int, aggregation: Aggregation,
                     evidence: list[Evidence]) -> tuple[bool, str]:
        bar = self.exit_bars.get(tier)
        if bar is None:
            return False, ""

        p = aggregation.posterior_false
        extremity = max(p, 1.0 - p)
        heading_false = p >= 0.5

        # Accusing someone early costs more than saving a few seconds, so the
        # bar to stop while heading toward FALSE is the higher one.
        multiplier = (self.false_exit_multiplier if heading_false
                      else self.unverified_exit_multiplier)
        required = bar * multiplier

        if extremity < required:
            return False, ""

        if not heading_false and self._confirmation_still_possible(tier, evidence):
            # The arithmetic is reassuring, but nothing has actually verified
            # this claim yet and an agent that could is still ahead. Exiting
            # here would return UNVERIFIED for a notice we were one tier away
            # from confirming — and would make TRUE unreachable in practice
            # while looking perfectly reachable in the config.
            return False, ""

        direction = "toward FALSE" if heading_false else "away from FALSE"
        return True, (f"extremity {extremity:.3f} cleared the tier-{tier} bar "
                      f"{required:.3f} {direction}")

    def _confirmation_still_possible(self, tier: int, evidence: list[Evidence]) -> bool:
        already = any(e.agent in self.confirming_agents and e.status == "ok"
                      and e.signal == "supports" for e in evidence)
        if already:
            return False
        return any(a.name in self.confirming_agents
                   for t in self.tiers if t > tier
                   for a in self.tiers[t])
