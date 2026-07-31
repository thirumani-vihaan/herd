"""Tests for Tier 3 — the terminal, network-bound research agent.

This agent was shipped calling `post_json(url, params=..., json=..., timeout=...)`
against a fetcher whose signature is `(url, *, json, timeout)`. Every call raised
TypeError, the broad except turned it into "unavailable", and no test noticed
because none existed.

The first test below is deliberately about the *call*, not the result: a fake
fetcher that mirrors the real signature is the cheapest possible guard against
an interface drifting away from its only caller.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.contracts import Claim, ClaimType, Entities, Strain
from app.investigate.agents.tier3 import OpenWebResearch

HERE = "vnrvjiet"


def claim(text: str = "The placement drive on Friday was cancelled") -> Claim:
    return Claim(id="c", report_id="r", institution_id=HERE,
                 claim_type=ClaimType.PLACEMENT, text=text, text_en=text,
                 language="en", entities=Entities(),
                 extraction_confidence=0.9,
                 extracted_at=datetime.now(timezone.utc))


def strain() -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id="s", first_seen=now, last_seen=now, report_count=1)


def response(signal: str, finding: str = "Found it.", *, citations: int = 1) -> dict:
    body = {"candidates": [{
        "content": {"parts": [{"text": json.dumps(
            {"signal": signal, "finding": finding})}]},
        "groundingMetadata": {"groundingChunks": [
            {"web": {"uri": f"https://example.org/{i}", "title": f"Source {i}"}}
            for i in range(citations)
        ]},
    }]}
    return body


class Fetcher:
    """Mirrors HttpFetcher.post_json exactly. Any extra kwarg is a TypeError."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.urls: list[str] = []
        self.bodies: list[dict] = []

    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0) -> dict:
        self.urls.append(url)
        self.bodies.append(json)
        return self.payload


def agent(fetcher, key: str = "TESTKEY") -> OpenWebResearch:
    a = OpenWebResearch(fetcher)
    a.api_key = key
    return a


async def test_it_calls_the_fetcher_with_the_signature_the_fetcher_actually_has():
    """The regression guard. This is the whole reason Tier 3 was dead."""
    f = Fetcher(response("contradicts"))
    ev = await agent(f).run(claim(), strain())

    assert ev.status == "ok", f"agent degraded instead of answering: {ev.error}"
    assert f.urls, "the fetcher was never called"
    # The API key has to travel somewhere; with no `params` support it belongs
    # in the query string.
    assert "key=TESTKEY" in f.urls[0]


async def test_a_grounded_contradiction_is_reported_with_its_citations():
    f = Fetcher(response("contradicts", "No such notice was published.", citations=2))
    ev = await agent(f).run(claim(), strain())

    assert ev.status == "ok"
    assert ev.signal == "contradicts"
    assert ev.strength > 0.0
    assert len(ev.sources) == 2
    assert all(s.kind == "web" for s in ev.sources)


async def test_a_grounded_support_is_reported():
    f = Fetcher(response("supports", citations=1))
    ev = await agent(f).run(claim(), strain())

    assert ev.status == "ok"
    assert ev.signal == "supports"
    assert ev.strength > 0.0


async def test_an_uncited_direction_is_downgraded_to_neutral():
    """Cite-or-stay-silent, applied to a model that asserts without grounding.

    The model is perfectly capable of returning "contradicts" with no grounding
    chunks. Emitting that would be an accusation with no source behind it, which
    is the one thing this project will not do.
    """
    f = Fetcher(response("contradicts", "Trust me.", citations=0))
    ev = await agent(f).run(claim(), strain())

    assert ev.status == "ok"
    assert ev.signal == "neutral"
    assert ev.strength == 0.0
    assert not ev.sources


async def test_an_unknown_signal_is_treated_as_neutral():
    f = Fetcher(response("definitely-fake", citations=1))
    ev = await agent(f).run(claim(), strain())

    assert ev.signal == "neutral"
    assert ev.strength == 0.0


async def test_no_text_means_no_research():
    f = Fetcher(response("contradicts"))
    ev = await agent(f).run(claim(text=""), strain())

    assert ev.status == "ok"
    assert ev.signal == "neutral"
    assert not f.urls, "an empty claim should not cost a network call"


async def test_it_asks_for_web_grounding():
    f = Fetcher(response("neutral"))
    await agent(f).run(claim(), strain())

    assert "tools" in f.bodies[0], "web research must actually request search"


async def test_a_malformed_response_degrades_instead_of_raising():
    class Garbage:
        async def post_json(self, url, *, json, timeout=8.0):
            return {"nothing": "useful"}

    ev = await agent(Garbage()).run(claim(), strain())

    assert ev.status == "unavailable"
    assert ev.signal == "neutral"
    assert ev.strength == 0.0


async def test_a_network_failure_degrades_instead_of_raising():
    class Down:
        async def post_json(self, url, *, json, timeout=8.0):
            raise RuntimeError("connection refused")

    ev = await agent(Down()).run(claim(), strain())

    assert ev.status == "unavailable"
    assert ev.error and "connection refused" in ev.error


async def test_without_an_api_key_the_agent_does_not_apply():
    assert not agent(Fetcher(response("neutral")), key="").applies_to(claim())
