"""Tier 3 terminal research agent."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app.config import get_settings, get_thresholds
from app.contracts import Claim, Evidence, Source, Strain
from app.interfaces import InvestigationAgent, HttpFetcher
from app.clients.featherless import FeatherlessClient


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class OpenWebResearch(InvestigationAgent):
    name = "OpenWebResearch"
    tier = 3
    correlation_group = "independent"

    def __init__(self, fetcher: HttpFetcher, featherless: FeatherlessClient) -> None:
        self.fetcher = fetcher
        self.featherless = featherless
        self.settings = get_settings()
        th = get_thresholds()
        self.strength = th.f("aggregation.reliability.OpenWebResearch")
        self.tavily_api_key = self.settings.tavily_api_key
        self.timeout = th.f("agents.open_web_research.timeout_s")

    def applies_to(self, claim: Claim) -> bool:
        return bool(self.tavily_api_key and self.featherless.available())

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            return await self._run(claim, started)
        except Exception as exc:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="open web research failed", sources=[],
                correlation_group=self.correlation_group, elapsed_ms=_ms(started),
                error=str(exc)[:200])

    async def _run(self, claim: Claim, started: float) -> Evidence:
        if not claim.text:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="neutral", strength=0.0,
                finding="no text to research", sources=[],
                correlation_group=self.correlation_group, elapsed_ms=_ms(started))

        # Step 1: Retrieve Live Web Data (The "R" in RAG) via Tavily
        tavily_url = "https://api.tavily.com/search"
        tavily_payload = {
            "api_key": self.tavily_api_key,
            "query": f"Fact-check: {claim.text}",
            "search_depth": "basic",
            "max_results": 3
        }
        
        search_resp = await self.fetcher.post_json(
            tavily_url, json=tavily_payload, timeout=self.timeout
        )
        
        results = search_resp.get("results", [])
        if not results:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="neutral", strength=0.0,
                finding="web research returned no results", sources=[],
                correlation_group=self.correlation_group, elapsed_ms=_ms(started))

        # Step 2: Bundle the Context
        context_parts = []
        sources = []
        for i, res in enumerate(results):
            title = res.get("title", f"Source {i+1}")
            url = res.get("url", "")
            content = res.get("content", "")
            if not url or not content:
                continue
                
            context_parts.append(f"Source {i+1}: {title}\nURL: {url}\nContent: {content}")
            sources.append(Source(
                url=url,
                title=title,
                excerpt="",
                retrieved_at=datetime.now(timezone.utc),
                kind="web"
            ))
            
        bundled_context = "\n\n".join(context_parts)
        
        # Step 3: Generate the AI Judgement (The "G" in RAG) via Featherless
        prompt = (
            f"Fact-check this claim: \"{claim.text}\"\n"
            f"Here is the context retrieved from the live open web:\n"
            f"---\n{bundled_context}\n---\n"
            "Based STRICTLY on the provided web context, decide if the results SUPPORT or CONTRADICT the claim, "
            "or if the context is NEUTRAL. \n"
            "Return JSON with exactly two keys: \n"
            "1. 'signal' (must be 'supports', 'contradicts', or 'neutral')\n"
            "2. 'finding' (a summary of the facts found, citing them as Source 1, Source 2, etc.)"
        )
        
        llm_resp = await self.featherless.chat(prompt, timeout=self.timeout)
        
        # Step 4: Parse and Return
        try:
            # Clean possible markdown formatting
            raw_text = llm_resp.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json")[1].rsplit("```", 1)[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].rsplit("```", 1)[0].strip()
                
            parsed = json.loads(raw_text)
            signal = parsed.get("signal", "neutral")
            if signal not in ("supports", "contradicts", "neutral"):
                signal = "neutral"
            finding = parsed.get("finding", "Completed web research.")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unexpected llm response format: {exc}") from exc

        # Cite-or-stay-silent: grounding can come back empty even when the model
        # asserts a direction. An uncited direction is exactly the thing this
        # project refuses to emit, so it degrades to neutral rather than being
        # rejected by the contract and swallowed as "unavailable".
        if signal != "neutral" and not sources:
            signal = "neutral"
            finding = f"web research returned no citable sources; not asserting a direction ({finding})"[:500]

        # If it's neutral, strength is 0
        actual_strength = self.strength if signal != "neutral" else 0.0

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal=signal, strength=actual_strength,
            finding=finding,
            sources=sources,
            correlation_group=self.correlation_group, elapsed_ms=_ms(started)
        )
