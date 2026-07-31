"""Featherless.ai LLM client for verdict prose generation.

Featherless provides OpenAI-compatible inference over open-source models.
HERD uses it as the **prose synthesis engine**: the verdict label is always
computed arithmetically by the aggregator, but the human-readable summary
and reasoning paragraph are written by a Featherless-hosted LLM.

This separation is deliberate — the verdict is deterministic (not LLM-dependent),
while the explanation benefits from a model that can weave evidence into
coherent prose. Using an open-source model via Featherless means the prose
layer is transparent, auditable, and not locked to any proprietary API.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from app.contracts import Claim, Evidence
from app.interfaces import HttpFetcher

logger = logging.getLogger(__name__)


class FeatherlessClient:
    """OpenAI-compatible client for Featherless.ai inference.

    Used for verdict prose synthesis — turning structured evidence into
    human-readable explanations. The verdict label itself is never produced
    by this client; it is computed deterministically by the aggregator.
    """

    def __init__(
        self,
        fetcher: HttpFetcher,
        api_key: str,
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        base_url: str = "https://api.featherless.ai/v1",
    ) -> None:
        self.fetcher = fetcher
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self.api_key)

    async def write_prose(
        self, *, label: str, evidence: Sequence[Evidence], claim: Claim
    ) -> dict[str, str]:
        """Generate human-readable verdict prose from structured evidence.

        The label is already decided by deterministic log-odds aggregation.
        This method only writes the explanation — it never changes the verdict.
        """
        if not self.available():
            return {"summary": "", "reasoning": ""}

        ev_text = "\n".join(
            f"- {e.agent} ({e.signal}): {e.finding}"
            for e in evidence
            if e.status == "ok"
        )

        system_prompt = (
            "You are a factual reporting agent for HERD, a campus misinformation "
            "detection system. You summarise investigation evidence into clear, "
            "cited prose. You NEVER invent facts. You NEVER change the verdict. "
            "You only explain WHY the evidence leads to the given conclusion."
        )

        user_prompt = (
            f"The verdict for this claim has been arithmetically calculated as: **{label}**\n\n"
            f"Claim: {claim.text}\n\n"
            f"Evidence found:\n{ev_text}\n\n"
            "Write exactly two fields in JSON:\n"
            "1. 'summary': A one-sentence explanation of why this verdict was reached, referencing the evidence.\n"
            "2. 'reasoning': A paragraph detailing the findings. Do NOT invent information. "
            "You MUST ONLY use the provided evidence.\n\n"
            "Return ONLY valid JSON with 'summary' and 'reasoning' keys."
        )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            resp = await self.fetcher.post_json(
                url, json=payload, headers=headers, timeout=15
            )
            raw = resp["choices"][0]["message"]["content"]

            # Strip markdown fences if present
            if raw.startswith("```json"):
                raw = raw.split("```json")[1].rsplit("```", 1)[0].strip()
            elif raw.startswith("```"):
                raw = raw.split("```")[1].rsplit("```", 1)[0].strip()

            parsed = json.loads(raw)
            return {
                "summary": parsed.get("summary", ""),
                "reasoning": parsed.get("reasoning", ""),
            }
        except Exception as exc:
            logger.warning("Featherless prose generation failed: %s", exc)
            return {"summary": "", "reasoning": ""}

    async def chat(self, prompt: str, *, system: str = "", timeout: float = 15) -> str:
        """General-purpose chat completion for any downstream use."""
        if not self.available():
            return ""

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            resp = await self.fetcher.post_json(
                url, json=payload, headers=headers, timeout=timeout
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Featherless chat failed: %s", exc)
            return ""
