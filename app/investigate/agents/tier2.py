"""Tier 2 agents: semantic retrieval from institution sources."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.config import get_thresholds
from app.contracts import Claim, Evidence, Strain, Institution, Source
from app.interfaces import InvestigationAgent, VectorIndex, EmbeddingModel


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class InstitutionalSource(InvestigationAgent):
    name = "InstitutionalSource"
    tier = 2
    correlation_group = "official"

    def __init__(self, institution: Institution, index: VectorIndex,
                 embeddings: EmbeddingModel, similarity_threshold: float | None = None) -> None:
        self.institution = institution
        self.index = index
        self.embeddings = embeddings
        th = get_thresholds()
        self.similarity_threshold = (th.f("agents.institutional_source.similarity_threshold")
                                     if similarity_threshold is None else similarity_threshold)
        self.cap_contradicts = th.f("aggregation.caps.InstitutionalSource.contradicts")
        self.cap_supports = th.f("aggregation.caps.InstitutionalSource.supports")

    def applies_to(self, claim: Claim) -> bool:
        return bool(self.institution.sources)

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            return await self._run(claim, started)
        except Exception as exc:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="institutional source search unavailable", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started),
                error=str(exc)[:200])

    async def _run(self, claim: Claim, started: float) -> Evidence:
        text = claim.text or ""
        if not text:
            return self._neutral(claim, started, "no text to search")

        vec = self.embeddings.encode([text])[0]
        namespace = f"{self.institution.id}_sources"
        results = self.index.query(vec, namespace=namespace, k=1)

        if results and results[0][1] >= self.similarity_threshold:
            match_id, score = results[0]
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="supports", strength=self.cap_supports,
                finding=f"found matching notice on official source (similarity: {score:.2f})",
                sources=[Source(
                    url=f"herd://source/{match_id}",
                    title="Official Institution Source",
                    excerpt="matched claim text",
                    retrieved_at=datetime.now(timezone.utc),
                    kind="source"
                )],
                correlation_group=self.correlation_group,
                elapsed_ms=_ms(started)
            )

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="contradicts", strength=self.cap_contradicts,
            finding="could not find this notice on any official institution source",
            sources=[],
            correlation_group=self.correlation_group,
            elapsed_ms=_ms(started)
        )

    def _neutral(self, claim: Claim, started: float, msg: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="neutral", strength=0.0, finding=msg, sources=[],
            correlation_group="independent", elapsed_ms=_ms(started))


class OfficialChannel(InvestigationAgent):
    name = "OfficialChannel"
    tier = 2
    correlation_group = "official"

    def __init__(self, institution: Institution, index: VectorIndex,
                 embeddings: EmbeddingModel, similarity_threshold: float | None = None) -> None:
        self.institution = institution
        self.index = index
        self.embeddings = embeddings
        th = get_thresholds()
        self.similarity_threshold = (th.f("agents.official_channel.similarity_threshold")
                                     if similarity_threshold is None else similarity_threshold)
        self.cap_contradicts = th.f("aggregation.caps.OfficialChannel.contradicts")
        self.cap_supports = th.f("aggregation.caps.OfficialChannel.supports")

    def applies_to(self, claim: Claim) -> bool:
        return bool(self.institution.official_channels)

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            return await self._run(claim, started)
        except Exception as exc:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="official channel search unavailable", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started),
                error=str(exc)[:200])

    async def _run(self, claim: Claim, started: float) -> Evidence:
        text = claim.text or ""
        if not text:
            return self._neutral(claim, started, "no text to search")

        vec = self.embeddings.encode([text])[0]
        namespace = f"{self.institution.id}_channels"
        results = self.index.query(vec, namespace=namespace, k=1)

        if results and results[0][1] >= self.similarity_threshold:
            match_id, score = results[0]
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="supports", strength=self.cap_supports,
                finding=f"found matching broadcast on official channel (similarity: {score:.2f})",
                sources=[Source(
                    url=f"herd://channel/{match_id}",
                    title="Official Channel Broadcast",
                    excerpt="matched claim text",
                    retrieved_at=datetime.now(timezone.utc),
                    kind="source"
                )],
                correlation_group=self.correlation_group,
                elapsed_ms=_ms(started)
            )

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="contradicts", strength=self.cap_contradicts,
            finding="could not find this broadcast on any official channel",
            sources=[],
            correlation_group=self.correlation_group,
            elapsed_ms=_ms(started)
        )

    def _neutral(self, claim: Claim, started: float, msg: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="neutral", strength=0.0, finding=msg, sources=[],
            correlation_group="independent", elapsed_ms=_ms(started))
