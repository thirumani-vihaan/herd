"""Tier 2 agents: semantic retrieval from institution sources."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.config import get_thresholds
from app.contracts import Claim, Evidence, Strain, Institution, Source
from app.interfaces import InvestigationAgent, VectorIndex, EmbeddingModel


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _source_citations(institution: Institution, note: str) -> list[Source]:
    """Cite the official sources that were searched.

    A 'not found on any official source' finding is a claim about absence, and
    cite-or-stay-silent applies to it exactly as it does to a positive finding.
    The honest citation is the list of places we actually looked.
    """
    now = datetime.now(timezone.utc)
    return [Source(url=s.url, title=f"Official source: {s.id}", excerpt=note,
                   retrieved_at=now, kind="institutional")
            for s in institution.sources]


def _channel_citations(institution: Institution, note: str) -> list[Source]:
    now = datetime.now(timezone.utc)
    out: list[Source] = []
    for c in institution.official_channels:
        value = str(c.value)
        url = value if "://" in value else f"https://{value}"
        out.append(Source(url=url, title=f"Official channel: {c.kind}", excerpt=note,
                          retrieved_at=now, kind="institutional"))
    return out


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
                sources=_source_citations(
                    self.institution,
                    f"matched index entry {match_id} at similarity {score:.2f}"),
                correlation_group=self.correlation_group,
                elapsed_ms=_ms(started)
            )

        citations = _source_citations(
            self.institution, "searched; no matching notice found")
        if not citations:
            return self._neutral(claim, started,
                                 "no official sources configured to search")

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="contradicts", strength=self.cap_contradicts,
            finding="could not find this notice on any official institution source",
            sources=citations,
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
                sources=_channel_citations(
                    self.institution,
                    f"matched index entry {match_id} at similarity {score:.2f}"),
                correlation_group=self.correlation_group,
                elapsed_ms=_ms(started)
            )

        citations = _channel_citations(
            self.institution, "searched; no matching broadcast found")
        if not citations:
            return self._neutral(claim, started,
                                 "no official channels configured to search")

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="contradicts", strength=self.cap_contradicts,
            finding="could not find this broadcast on any official channel",
            sources=citations,
            correlation_group=self.correlation_group,
            elapsed_ms=_ms(started)
        )

    def _neutral(self, claim: Claim, started: float, msg: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal="neutral", strength=0.0, finding=msg, sources=[],
            correlation_group="independent", elapsed_ms=_ms(started))
