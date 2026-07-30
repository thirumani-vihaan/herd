"""StrainPrior: what HERD already knows about this template (ADR-0026).

This is the agent the whole recognition layer exists to feed. When a claim is
recognised as a mutation of a strain investigated last week — possibly at a
different college — the cascade does not rediscover it, and the answer arrives
in milliseconds instead of seconds.

It is also the agent most capable of systemic harm, for exactly the same
reason: a wrong verdict on a popular strain would propagate to every
institution that later saw it. Four constraints follow, none optional.

SCOPE. ADR-0026 makes evidence institution-scoped and strain memory global.
This agent honours that boundary literally. It reads THIS institution's own
verdict record in full, and for every other institution it reads only the
`local_verdict` label recorded on the sighting — never their evidence, never
their reasoning, never their confidence. Reaching across for the full record
would be easy and would quietly undo the scoping decision.

STANDING. Cross-institution history is listed in
`verdict.cannot_conclude_alone`, so it can shorten an investigation but can
never be one. One campus's mistake must not become every campus's verdict.

WEIGHT. History here is stronger evidence than history elsewhere, because here
we know how the conclusion was reached.

HONESTY ABOUT UNCERTAINTY. A strain whose own verdict was UNVERIFIED
contributes nothing. Inheriting an abstention as though it were a finding is
how uncertainty gets laundered into confidence.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.config import get_thresholds
from app.contracts import Claim, Evidence, Source, Strain, VerdictLabel
from app.interfaces import InvestigationAgent, Store

DECISIVE = (VerdictLabel.FALSE, VerdictLabel.MISLEADING, VerdictLabel.TRUE)


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class StrainPrior(InvestigationAgent):
    """Tier 0: a local memory lookup, which is why it costs nothing.

    It sits at Tier 0 rather than later precisely because its purpose is to
    make the expensive tiers unnecessary. A memory that only consults itself
    after the money has been spent is not saving anything.
    """

    name = "StrainPrior"
    tier = 0
    correlation_group = "memory"

    def __init__(self, store: Store, institution_id: str,
                 same_institution_weight: float | None = None,
                 cross_institution_weight: float | None = None) -> None:
        self.store = store
        self.institution_id = institution_id
        th = get_thresholds()
        self.same_weight = (th.f("aggregation.strain_prior.same_institution")
                            if same_institution_weight is None else same_institution_weight)
        self.cross_weight = (th.f("aggregation.strain_prior.cross_institution")
                             if cross_institution_weight is None else cross_institution_weight)

    def applies_to(self, claim: Claim) -> bool:
        return True

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            return await self._run(claim, strain, started)
        except Exception as exc:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="strain memory unavailable", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started),
                error=str(exc)[:200])

    async def _run(self, claim: Claim, strain: Strain, started: float) -> Evidence:
        lineage = await self._lineage(strain)

        local = await self._local_finding(lineage)
        if local is not None:
            return self._evidence(claim, started, *local)

        remote = self._remote_finding(lineage)
        if remote is not None:
            return self._evidence(claim, started, *remote)

        seen_anywhere = sum(len(s.seen_at) for s in lineage)
        if seen_anywhere:
            return self._neutral(
                claim, started,
                "this template has been seen before but never resolved, so it "
                "carries no conclusion to reuse")
        return self._neutral(claim, started,
                             "this template has not been investigated before")

    # -- this institution's own record, read in full ------------------------

    async def _local_finding(self, lineage: list[Strain]):
        for strain in lineage:
            verdict = await self.store.get_verdict(strain.id, self.institution_id)
            if verdict is None or verdict.label not in DECISIVE:
                continue
            # A verdict HERD was unsure about must not become a confident prior
            # for the next claim. Uncertainty compounds; it does not reset.
            weight = round(self.same_weight * float(verdict.confidence), 4)
            if weight <= 0:
                continue
            inherited = strain.id != lineage[0].id
            verb = ("was confirmed genuine" if verdict.label is VerdictLabel.TRUE
                    else f"was found {verdict.label.value.lower()}")
            finding = (f"this institution already investigated "
                       f"{'an earlier version of ' if inherited else ''}this exact "
                       f"template and it {verb}, with "
                       f"{verdict.confidence:.0%} confidence")
            signal = "supports" if verdict.label is VerdictLabel.TRUE else "contradicts"
            return signal, weight, finding, strain, "this institution"
        return None

    # -- other institutions: the label on the sighting, and nothing else -----

    def _remote_finding(self, lineage: list[Strain]):
        best = None
        for strain in lineage:
            for sighting in strain.seen_at:
                if sighting.institution_id == self.institution_id:
                    continue
                if sighting.local_verdict not in DECISIVE:
                    continue
                # More reports behind a sighting is a stronger observation, but
                # only weakly so: it is still one institution's conclusion.
                if best is None or sighting.report_count > best[1].report_count:
                    best = (strain, sighting)
        if best is None:
            return None

        strain, sighting = best
        label = sighting.local_verdict
        signal = "supports" if label is VerdictLabel.TRUE else "contradicts"
        verb = ("was confirmed genuine" if label is VerdictLabel.TRUE
                else f"was found {label.value.lower()}")
        finding = (f"another institution reported this same template "
                   f"{sighting.report_count} time(s) and it {verb} there. "
                   f"Cross-institution history cannot decide this claim on its "
                   f"own — it only says where to look first")
        return signal, self.cross_weight, finding, strain, "another institution"

    # -- helpers -----------------------------------------------------------

    async def _lineage(self, strain: Strain) -> list[Strain]:
        """This strain and its ancestors, nearest first.

        A child strain is the same operation with a mutated payload, so its
        ancestors' history is this claim's history. Guarded against a cycle in
        `parent_id`, because a lineage loop would otherwise hang an entire
        investigation on a memory lookup.
        """
        chain: list[Strain] = [strain]
        seen = {strain.id}
        current = strain
        while current.parent_id and current.parent_id not in seen:
            parent = await self.store.get_strain(current.parent_id)
            if parent is None:
                break
            seen.add(parent.id)
            chain.append(parent)
            current = parent
        return chain

    def _evidence(self, claim: Claim, started: float, signal: str, strength: float,
                  finding: str, strain: Strain, where: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal=signal, strength=strength, finding=finding,
            sources=[Source(
                url=f"herd://strain/{strain.id}",
                title=f"Prior verdict on this template, {where}",
                excerpt=finding, retrieved_at=datetime.now(timezone.utc),
                kind="memory")],
            correlation_group=self.correlation_group, elapsed_ms=_ms(started))

    def _neutral(self, claim: Claim, started: float, msg: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="neutral", strength=0.0, finding=msg, sources=[],
            correlation_group="independent", elapsed_ms=_ms(started))
