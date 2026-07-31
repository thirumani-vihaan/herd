"""Interfaces. Every external dependency sits behind one of these.

Each ABC names, in its docstring, the exact place its real implementation is
constructed. That line is what `tools/check_wiring.py` verifies — an interface
with no real implementation wired in is a fake that shipped.

FROZEN after T011 (L4).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.contracts import Claim, Evidence, Report, Strain


class LLMClient(ABC):
    """Multimodal extraction and prose. NEVER produces a label (ADR-0013).

    Real impl: app/clients/gemini.py:GeminiClient, constructed in
    app/wiring.py:build_container.
    """

    @abstractmethod
    async def extract_claim(self, *, image_bytes: bytes | None, text: str | None,
                            institution_short_name: str) -> dict[str, Any]:
        """Return a raw dict for Claim validation. Must never raise."""

    @abstractmethod
    async def write_prose(self, *, label: str, evidence: Sequence[Evidence],
                          claim: Claim) -> dict[str, str]:
        """Prose only, after the label is already fixed. Must never raise."""

    @abstractmethod
    def available(self) -> bool:
        ...


class EmbeddingModel(ABC):
    """Dual-vector multilingual embedding (ADR-0006).

    Real impl: app/clients/embeddings.py:SentenceTransformerEmbeddings,
    constructed in app/wiring.py:build_container.
    """

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        ...


class VectorIndex(ABC):
    """Strain centroid search (ADR-0010).

    Real impl: app/clients/vector.py:ChromaVectorIndex, constructed in
    app/wiring.py:build_container.
    """

    @abstractmethod
    def upsert(self, strain_id: str, vector: Sequence[float], namespace: str,
               metadata: dict[str, Any] | None = None) -> None:
        ...

    @abstractmethod
    def query(self, vector: Sequence[float], namespace: str, k: int = 5
              ) -> list[tuple[str, float]]:
        """Return (strain_id, cosine_similarity) descending."""

    @abstractmethod
    def count(self, namespace: str) -> int:
        ...


class Store(ABC):
    """Persistence (ADR-0022: SQLite + WAL behind this interface).

    Real impl: app/storage/sqlite_store.py:SqliteStore, constructed in
    app/wiring.py:build_container.
    """

    @abstractmethod
    async def init(self) -> None: ...

    @abstractmethod
    async def save_report(self, report: Report) -> None: ...

    @abstractmethod
    async def recent_duplicate(self, image_sha256: str | None, reporter_hash: str,
                               within_seconds: int) -> str | None:
        """Idempotency check, run BEFORE the spread model sees the report."""

    @abstractmethod
    async def save_claim(self, claim: Claim) -> None: ...

    @abstractmethod
    async def upsert_strain(self, strain: Strain) -> None: ...

    @abstractmethod
    async def get_strain(self, strain_id: str) -> Strain | None: ...

    @abstractmethod
    async def all_strains(self) -> list[Strain]: ...

    @abstractmethod
    async def reports_for_strain(self, strain_id: str, institution_id: str
                                 ) -> list[Report]: ...

    @abstractmethod
    async def save_verdict(self, verdict: Any) -> None: ...

    @abstractmethod
    async def get_verdict(self, strain_id: str, institution_id: str) -> Any | None: ...

    @abstractmethod
    async def override_verdict(self, strain_id: str, institution_id: str, label: str, overridden_by: str) -> None: ...

    @abstractmethod
    async def save_alert(self, alert: Any) -> None: ...

    @abstractmethod
    async def alerts_since(self, institution_id: str, hours: float) -> list[Any]: ...

    @abstractmethod
    async def link_report_to_strain(self, report_id: str, strain_id: str) -> None: ...


class HttpFetcher(ABC):
    """All outbound HTTP. Cassette-recordable (ADR-0023).

    Real impl: app/clients/http.py:HttpxFetcher, constructed in
    app/wiring.py:build_container.
    """

    @abstractmethod
    async def get_json(self, url: str, *, params: dict | None = None,
                       headers: dict | None = None, timeout: float = 8.0) -> dict:
        """Must never raise; returns {} and records the failure."""

    @abstractmethod
    async def get_text(self, url: str, *, timeout: float = 8.0) -> str:
        ...

    @abstractmethod
    async def post_json(self, url: str, *, json: dict, timeout: float = 8.0) -> dict:
        ...


class InvestigationAgent(ABC):
    """Returns evidence, never a verdict (ADR-0012, docs/03 agent contract).

    Real impls: app/investigate/agents/*.py, all constructed in
    app/wiring.py:build_container.
    """

    name: str = "Agent"
    tier: int = 0
    correlation_group: str = "independent"

    @abstractmethod
    def applies_to(self, claim: Claim) -> bool:
        """False means not_applicable: return immediately, cost nothing."""

    @abstractmethod
    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        """MUST NOT RAISE. Failure returns status='unavailable'."""


class Notifier(ABC):
    """Alert delivery (ADR-0021).

    Real impl: app/intervene/notifiers.py:{TelegramNotifier,WebSocketNotifier},
    constructed in app/wiring.py:build_container.
    """

    channel: str = "unknown"

    @abstractmethod
    async def send(self, alert: Any) -> int:
        """Return delivery count. Must never raise."""

    @abstractmethod
    def available(self) -> bool: ...


class Clock(ABC):
    """Injectable time, so the spread model is testable without sleeping.

    Real impl: app/clients/clock.py:SystemClock, constructed in
    app/wiring.py:build_container.
    """

    @abstractmethod
    def now(self): ...


__all__ = [
    "LLMClient", "EmbeddingModel", "VectorIndex", "Store", "HttpFetcher",
    "InvestigationAgent", "Notifier", "Clock",
]
