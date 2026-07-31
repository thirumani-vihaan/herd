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
            "You are a scam and misinformation verification agent. Extract the company or organization mentioned in the following claim.\n"
            f"Claim: \"{claim.text}\"\n\n"
            "Search the web to find the official career page, official website, or verified social media of that specific company.\n"
            "Verify if the specific internship or job mentioned actually exists on their official channels.\n"
            "If the official channels confirm it, output 'supports'.\n"
            "If the official channels exist but do NOT list this, or if the claim points to a fake domain, output 'contradicts'.\n"
            "If you cannot find the company or cannot verify, output 'neutral'.\n"
            "Return JSON with exactly two keys: 'signal' ('supports', 'contradicts', 'neutral') "
            "and 'finding' (a summary of your verification process and facts found, with citations). "
        )

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        resp = await self.fetcher.post_json(
            url,
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
                        kind="web"
                    ))
                    
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"unexpected gemini response format: {exc}") from exc

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
