"""In-memory doubles for the ports in app/interfaces.py.

These deliberately subclass the ABCs rather than duck-typing. A duck-typed fake
keeps passing after the real interface grows a method, which is precisely when
the tests stop meaning anything: they would be exercising a shape the
production code no longer has. Subclassing makes an interface change fail here
first, loudly, at import time.

They are also honest about *behaviour*, not just signatures — FakeStore's
`get_verdict` is institution-scoped exactly as SqliteStore's is (ADR-0026), so
a scope violation is reproducible without a database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.contracts import Claim, Report, Strain
from app.interfaces import Clock, HttpFetcher, Notifier, Store


class FakeStore(Store):
    """A dict-backed Store that records what was asked of it.

    `verdict_reads` exists so a test can assert not only that the answer was
    right but that the wrong data was never *fetched*. For ADR-0026 that
    distinction is the whole point: an agent that reads another institution's
    verdict and then chooses to ignore it has still crossed the boundary, and
    the next refactor will forget the ignoring part.
    """

    def __init__(self) -> None:
        self.reports: dict[str, Report] = {}
        self.claims: dict[str, Claim] = {}
        self.strains: dict[str, Strain] = {}
        self.verdicts: dict[tuple[str, str], Any] = {}
        self.alerts: list[Any] = []
        self.links: list[tuple[str, str]] = []
        self.verdict_reads: list[tuple[str, str]] = []
        self.raise_on_get_verdict: Exception | None = None

    async def init(self) -> None:
        return None

    async def save_report(self, report: Report) -> None:
        self.reports[report.id] = report

    async def recent_duplicate(self, image_sha256: str | None, reporter_hash: str,
                               within_seconds: int) -> str | None:
        if image_sha256 is None:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
        for r in self.reports.values():
            if (r.image_sha256 == image_sha256
                    and r.reporter_hash == reporter_hash
                    and r.received_at >= cutoff):
                return r.id
        return None

    async def save_claim(self, claim: Claim) -> None:
        self.claims[claim.id] = claim

    async def upsert_strain(self, strain: Strain) -> None:
        self.strains[strain.id] = strain

    async def get_strain(self, strain_id: str) -> Strain | None:
        return self.strains.get(strain_id)

    async def all_strains(self) -> list[Strain]:
        return list(self.strains.values())

    async def reports_for_strain(self, strain_id: str, institution_id: str
                                 ) -> list[Report]:
        return [r for (rid, sid) in self.links if sid == strain_id
                for r in [self.reports.get(rid)]
                if r is not None and r.institution_id == institution_id]

    async def save_verdict(self, verdict: Any) -> None:
        self.verdicts[(verdict.strain_id, verdict.institution_id)] = verdict

    async def get_verdict(self, strain_id: str, institution_id: str) -> Any | None:
        self.verdict_reads.append((strain_id, institution_id))
        if self.raise_on_get_verdict is not None:
            raise self.raise_on_get_verdict
        return self.verdicts.get((strain_id, institution_id))

    async def save_alert(self, alert: Any) -> None:
        self.alerts.append(alert)

    async def alerts_since(self, institution_id: str, hours: float) -> list[Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [a for a in self.alerts
                if getattr(a, "institution_id", None) == institution_id
                and getattr(a, "created_at", cutoff) >= cutoff]

    async def link_report_to_strain(self, report_id: str, strain_id: str) -> None:
        self.links.append((report_id, strain_id))


class OfflineFetcher(HttpFetcher):
    """Every call fails, the way a blocked network fails.

    The demo invariant is that HERD still produces a verdict with the network
    unplugged, so 'offline' needs to be a thing tests can assert against rather
    than a thing we hope agents handle.
    """

    def __init__(self, message: str = "network unavailable") -> None:
        self.message = message
        self.calls: list[str] = []

    async def get_json(self, url: str, *, params: dict | None = None,
                       timeout: float = 8.0) -> dict:
        self.calls.append(url)
        raise ConnectionError(self.message)

    async def get_text(self, url: str, *, timeout: float = 8.0) -> str:
        self.calls.append(url)
        raise ConnectionError(self.message)

    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0) -> dict:
        self.calls.append(url)
        raise ConnectionError(self.message)


class ScriptedFetcher(HttpFetcher):
    """Replays canned responses by URL substring; unmatched URLs go offline.

    Unmatched-means-offline is deliberate. A fetcher that returns `{}` for an
    unscripted URL lets a test pass while silently exercising a path the author
    never wrote a response for.
    """

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self.routes = routes or {}
        self.calls: list[str] = []

    def _match(self, url: str) -> Any:
        self.calls.append(url)
        for key, value in self.routes.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise ConnectionError(f"no route for {url}")

    async def get_json(self, url: str, *, params: dict | None = None,
                       timeout: float = 8.0) -> dict:
        return self._match(url)

    async def get_text(self, url: str, *, timeout: float = 8.0) -> str:
        return self._match(url)

    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0) -> dict:
        return self._match(url)


class CollectingNotifier(Notifier):
    """Records deliveries instead of making them."""

    channel = "collecting"

    def __init__(self, recipients: int = 1, *, available: bool = True) -> None:
        self.sent: list[Any] = []
        self.recipients = recipients
        self._available = available

    async def send(self, alert: Any) -> int:
        self.sent.append(alert)
        return self.recipients

    def available(self) -> bool:
        return self._available


class FrozenClock(Clock):
    """Time that only moves when a test moves it."""

    def __init__(self, at: datetime | None = None) -> None:
        self._now = at or datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> datetime:
        self._now = self._now + timedelta(**kwargs)
        return self._now
