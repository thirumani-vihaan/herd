"""The one place HERD touches the network (ADR-0023).

Everything network-shaped goes through this port so that "offline" is a single
switch rather than a property each agent has to remember to implement. That
matters more than it sounds: the demo invariant is that a network-blocked run
still produces a verdict, and an invariant that depends on nine agents each
handling `ConnectionError` correctly is an invariant that will break the first
time someone adds a tenth.

Failures are raised, not swallowed. Agents are required to degrade, and they
can only degrade if they are told something went wrong.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import get_settings

USER_AGENT = ("HERD/0.1 (campus misinformation immune system; "
              "contact: via institution profile)")


class HttpxFetcher:
    """Real network access, with a client that outlives a single call.

    A fresh `AsyncClient` per request would re-do TLS on every RDAP lookup and
    turn a 200 ms tier into a 2 s one. The client is created lazily so that
    importing this module never opens a socket — tests import it constantly.
    """

    def __init__(self, *, timeout: float = 8.0, retries: int = 1) -> None:
        self.timeout = timeout
        self.retries = retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=8))
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, url: str, *, timeout: float,
                       **kwargs) -> httpx.Response:
        client = await self._get_client()
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.request(method, url, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                # A 4xx is an answer, not a glitch. Retrying it wastes the
                # caller's deadline to receive the same refusal again.
                if exc.response.status_code < 500:
                    raise
                last = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = exc
            if attempt < self.retries:
                await asyncio.sleep(0.25 * (attempt + 1))
        raise last if last else RuntimeError("request failed without an exception")

    async def get_json(self, url: str, *, params: dict | None = None,
                       timeout: float = 8.0) -> dict:
        r = await self._request("GET", url, timeout=timeout, params=params)
        return r.json()

    async def get_text(self, url: str, *, timeout: float = 8.0) -> str:
        r = await self._request("GET", url, timeout=timeout)
        return r.text

    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0,
                        headers: dict | None = None) -> dict:
        r = await self._request("POST", url, timeout=timeout, json=json,
                                headers=headers)
        return r.json()


class BlockedFetcher:
    """Refuses every call, loudly.

    Used by `DEMO_MODE=offline` and by the demo-invariant test. It exists so
    "we tested the offline path" can mean something stronger than "we unplugged
    the wifi once and it seemed fine".
    """

    reason = "network access is disabled (DEMO_MODE=offline)"

    def __init__(self) -> None:
        self.attempts: list[str] = []

    async def get_json(self, url: str, *, params: dict | None = None,
                       timeout: float = 8.0) -> dict:
        self.attempts.append(url)
        raise ConnectionError(self.reason)

    async def get_text(self, url: str, *, timeout: float = 8.0) -> str:
        self.attempts.append(url)
        raise ConnectionError(self.reason)

    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0,
                        headers: dict | None = None) -> dict:
        self.attempts.append(url)
        raise ConnectionError(self.reason)

    async def aclose(self) -> None:
        return None


def build_fetcher(mode: str | None = None) -> Any:
    """The fetcher the container should use for the current mode."""
    resolved = (mode or get_settings().demo_mode or "live").lower()
    if resolved == "offline":
        return BlockedFetcher()
    return HttpxFetcher()
