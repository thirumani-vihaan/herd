"""Tier 3 terminal research agent."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app.config import get_settings, get_thresholds
from app.contracts import Claim, Evidence, Source, Strain
from app.interfaces import InvestigationAgent, HttpFetcher


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class OpenWebResearch(InvestigationAgent):
    name = "OpenWebResearch"
    tier = 3
    correlation_group = "independent"

    def __init__(self, fetcher: HttpFetcher) -> None:
        self.fetcher = fetcher
        self.settings = get_settings()
        th = get_thresholds()
        self.strength = th.f("aggregation.reliability.OpenWebResearch")
        self.model = self.settings.gemini_model
        self.api_key = self.settings.gemini_api_key
        self.timeout = th.f("agents.open_web_research.timeout_s")

    def applies_to(self, claim: Claim) -> bool:
        return bool(self.api_key)

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

        prompt = (
            f"Fact-check this claim concerning {claim.institution_id}:\n"
            f"\"{claim.text}\"\n\n"
            "Search the web. Decide if the search results SUPPORT or CONTRADICT the claim, "
            "or if it is NEUTRAL (unverifiable). "
            "Return JSON with exactly two keys: 'signal' (must be 'supports', 'contradicts', or 'neutral') "
            "and 'finding' (a summary of the facts found, with citations). "
            "Do not state a final true/false verdict, just summarize the evidence direction."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        resp = await self.fetcher.post_json(
            url,
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout
        )

        try:
            cand = resp["candidates"][0]
            raw_text = cand["content"]["parts"][0]["text"]
            
            # The model might return markdown json blocks
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json")[1].rsplit("```", 1)[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].rsplit("```", 1)[0].strip()
                
            parsed = json.loads(raw_text)
            signal = parsed.get("signal", "neutral")
            if signal not in ("supports", "contradicts", "neutral"):
                signal = "neutral"
                
            finding = parsed.get("finding", "Completed web research.")
            
            sources = []
            grounding = cand.get("groundingMetadata", {})
            chunks = grounding.get("groundingChunks", [])
            for i, chunk in enumerate(chunks):
                web = chunk.get("web", {})
                if web and "uri" in web:
                    sources.append(Source(
                        url=web["uri"],
                        title=web.get("title", f"Web Source {i+1}"),
                        excerpt="",
                        retrieved_at=datetime.now(timezone.utc),
                        kind="news"
                    ))
                    
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"unexpected gemini response format: {exc}") from exc

        # If it's neutral, strength is 0
        actual_strength = self.strength if signal != "neutral" else 0.0

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal=signal, strength=actual_strength,
            finding=finding,
            sources=sources,
            correlation_group=self.correlation_group, elapsed_ms=_ms(started)
        )
