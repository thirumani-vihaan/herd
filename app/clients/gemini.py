"""Gemini LLM Client for extraction and prose generation."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Sequence

from app.contracts import Claim, Evidence
from app.interfaces import LLMClient, HttpFetcher
from app.perceive.extract import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """Real Gemini client using the REST API."""

    def __init__(self, fetcher: HttpFetcher, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        self.fetcher = fetcher
        self.api_key = api_key
        self.model = model_name
        
        from app.config import get_thresholds
        self.timeout = get_thresholds().f("agents.llm_client.timeout_s")

    def available(self) -> bool:
        return bool(self.api_key)

    async def extract_claim(self, *, image_bytes: bytes | None, text: str | None,
                            institution_short_name: str) -> dict[str, Any]:
        if not self.available():
            return {}

        prompt = EXTRACTION_PROMPT.format(institution=institution_short_name)
        if text:
            prompt += f"\n\nMessage text:\n{text}"
        
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": b64
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        
        try:
            resp = await self.fetcher.post_json(
                url,
                json=payload,
                timeout=self.timeout
            )
            cand = resp["candidates"][0]
            raw = cand["content"]["parts"][0]["text"]
            
            # Handle possible markdown wrap
            if raw.startswith("```json"):
                raw = raw.split("```json")[1].rsplit("```", 1)[0].strip()
            elif raw.startswith("```"):
                raw = raw.split("```")[1].rsplit("```", 1)[0].strip()
                
            return json.loads(raw)
        except Exception as exc:
            logger.error("Failed to extract claim: %s", exc)
            return {}

    async def write_prose(self, *, label: str, evidence: Sequence[Evidence],
                          claim: Claim) -> dict[str, str]:
        if not self.available():
            return {"summary": "", "reasoning": ""}
            
        ev_text = "\n".join(f"- {e.agent} ({e.signal}): {e.finding}" for e in evidence if e.status == "ok")
        
        prompt = (
            f"You are a factual reporting agent. A claim has been investigated and the strict label "
            f"has been arithmetically calculated as: {label}\n\n"
            f"Claim: {claim.text}\n\n"
            f"Evidence found:\n{ev_text}\n\n"
            "Write exactly two fields in JSON:\n"
            "1. 'summary': A one-sentence explanation of why this verdict was reached, referencing the evidence.\n"
            "2. 'reasoning': A paragraph detailing the findings. Do NOT invent information. "
            "You MUST ONLY use the provided evidence."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        
        try:
            resp = await self.fetcher.post_json(
                url,
                json=payload,
                timeout=self.timeout
            )
            cand = resp["candidates"][0]
            raw = cand["content"]["parts"][0]["text"]
            
            if raw.startswith("```json"):
                raw = raw.split("```json")[1].rsplit("```", 1)[0].strip()
            elif raw.startswith("```"):
                raw = raw.split("```")[1].rsplit("```", 1)[0].strip()
                
            parsed = json.loads(raw)
            return {
                "summary": parsed.get("summary", ""),
                "reasoning": parsed.get("reasoning", "")
            }
        except Exception as exc:
            logger.error("Failed to write prose: %s", exc)
            return {"summary": "", "reasoning": ""}
