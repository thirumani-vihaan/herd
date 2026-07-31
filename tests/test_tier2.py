"""Tests for Tier 2 — the only agents allowed to confirm a claim (ADR-0028).

These tests exist because their absence was expensive. Both Tier 2 agents once
shipped in a state where every single code path returned `status="unavailable"`,
and the suite stayed green through it. Two things hid it:

  1. `run()` wraps `_run()` in a broad `except Exception -> unavailable`, so a
     contract violation inside the agent became a quiet degradation instead of
     a loud failure.
  2. Nothing tested these agents at all.

So the rule these tests encode is: **assert on the status field, not just on the
signal**. An agent that answers "unavailable" to everything will satisfy any
test that only checks "it did not accuse anyone".
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.contracts import (Channel, Claim, ClaimType, Domains, Entities,
                           Institution, InstitutionSource, PaymentSpec, Strain)
from app.investigate.agents.tier2 import InstitutionalSource, OfficialChannel

HERE = "vnrvjiet"


def institution(*, sources: bool = True, channels: bool = True) -> Institution:
    return Institution(
        id=HERE, display_name="VNR VJIET", short_name="vnrvjiet",
        domains=Domains(official=["vnrvjiet.ac.in"], email=["vnrvjiet.in"]),
        payments=PaymentSpec(verified=False, official_upi_handles=[]),
        sources=[InstitutionSource(
            id="placements", url="https://www.vnrvjiet.ac.in/placements",
            kind="html", topics=["placement"], refresh="6h", authority=1.0,
        )] if sources else [],
        official_channels=[Channel(
            kind="website", value="vnrvjiet.ac.in", note="notice board",
        )] if channels else [],
    )


def claim(text: str = "Placement drive on Friday") -> Claim:
    return Claim(id="c", report_id="r", institution_id=HERE,
                 claim_type=ClaimType.PLACEMENT, text=text, text_en=text,
                 language="en", entities=Entities(),
                 extraction_confidence=0.9,
                 extracted_at=datetime.now(timezone.utc))


def strain() -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id="s", first_seen=now, last_seen=now, report_count=1)


class Embeddings:
    def encode(self, texts):
        return [[0.1] * 8 for _ in texts]


class Index:
    """A vector index that either has a near-match or has nothing."""

    def __init__(self, score: float | None) -> None:
        self.score = score
        self.namespaces: list[str] = []

    def query(self, vector, namespace, k):
        self.namespaces.append(namespace)
        return [("notice_42", self.score)] if self.score is not None else []


AGENTS = [InstitutionalSource, OfficialChannel]


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_a_match_on_an_official_source_supports_the_claim(agent_cls):
    agent = agent_cls(institution(), Index(0.93), Embeddings())
    ev = await agent.run(claim(), strain())

    # status first: this is the assertion that would have caught the outage.
    assert ev.status == "ok", f"agent degraded instead of answering: {ev.error}"
    assert ev.signal == "supports"
    assert ev.strength > 0.0
    assert ev.sources, "a supporting finding must cite what it found"


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_no_match_contradicts_and_still_cites_where_it_looked(agent_cls):
    agent = agent_cls(institution(), Index(None), Embeddings())
    ev = await agent.run(claim(), strain())

    assert ev.status == "ok", f"agent degraded instead of answering: {ev.error}"
    assert ev.signal == "contradicts"
    # Cite-or-stay-silent applies to absence exactly as it does to presence.
    # "We could not find it" is only meaningful alongside where we looked.
    assert ev.sources, "a claim about absence must cite the sources searched"


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_a_below_threshold_match_is_not_treated_as_a_match(agent_cls):
    agent = agent_cls(institution(), Index(0.10), Embeddings())
    ev = await agent.run(claim(), strain())

    assert ev.status == "ok"
    assert ev.signal == "contradicts"


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_every_emitted_evidence_satisfies_the_contract(agent_cls):
    """The contract is the real test here.

    Both original defects (an invalid `Source.kind`, and a non-neutral finding
    with no sources) were *caught* by the validators — the broad except turned
    them into "unavailable". Constructing Evidence at all is the check; the
    status assertion is what stops it being swallowed.
    """
    for score in (0.93, None):
        agent = agent_cls(institution(), Index(score), Embeddings())
        ev = await agent.run(claim(), strain())
        assert ev.error is None, f"contract violation leaked: {ev.error}"
        for src in ev.sources:
            assert src.kind in {"web", "institutional", "registry",
                                "api", "rule", "memory"}


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_an_empty_claim_stays_silent_rather_than_contradicting(agent_cls):
    agent = agent_cls(institution(), Index(None), Embeddings())
    ev = await agent.run(claim(text=""), strain())

    assert ev.status == "ok"
    assert ev.signal == "neutral"
    assert ev.strength == 0.0


async def test_agents_do_not_apply_when_nothing_is_configured_to_search():
    assert not InstitutionalSource(
        institution(sources=False), Index(None), Embeddings()).applies_to(claim())
    assert not OfficialChannel(
        institution(channels=False), Index(None), Embeddings()).applies_to(claim())


async def test_each_agent_searches_its_own_namespace():
    idx = Index(None)
    await InstitutionalSource(institution(), idx, Embeddings()).run(claim(), strain())
    assert idx.namespaces == [f"{HERE}_sources"]

    idx2 = Index(None)
    await OfficialChannel(institution(), idx2, Embeddings()).run(claim(), strain())
    assert idx2.namespaces == [f"{HERE}_channels"]


@pytest.mark.parametrize("agent_cls", AGENTS)
async def test_an_index_failure_degrades_instead_of_raising(agent_cls):
    """The broad except is correct behaviour — one agent must not stop a run.

    What was wrong before was not the catch; it was that nothing distinguished
    a genuine outage from a bug. This test pins the intended use.
    """
    class Broken:
        def query(self, vector, namespace, k):
            raise RuntimeError("index offline")

    agent = agent_cls(institution(), Broken(), Embeddings())
    ev = await agent.run(claim(), strain())

    assert ev.status == "unavailable"
    assert ev.signal == "neutral"
    assert ev.strength == 0.0
    assert ev.error and "index offline" in ev.error
