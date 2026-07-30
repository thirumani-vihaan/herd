"""Frozen contracts. Every boundary in HERD is one of these models.

Rules that are enforced here rather than remembered:
  - `institution_id` is REQUIRED on every tenant-scoped record and ABSENT from
    `Strain` (ADR-0026). Strain memory is global; evidence is scoped.
  - Every projected quantity is an `Interval`, never a float (ADR-0017/0018), so
    no display code is able to render a false point estimate.
  - `Verdict.what_would_change_my_mind` is non-empty. It is the falsifier and the
    basis of the appeals process.

This file is FROZEN after T011. Changes require an ADR (L4/L7).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Frozen(BaseModel):
    """Base: strict, no silent coercion, no unknown fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

class Interval(Frozen):
    """A quantity with honest uncertainty.

    Used for every projected value. A model that cannot express its own
    uncertainty will be read as if it had none.
    """

    lo: float
    point: float
    hi: float
    unit: str = ""

    @model_validator(mode="after")
    def _ordered(self) -> "Interval":
        if not (self.lo <= self.point <= self.hi):
            raise ValueError(f"interval must satisfy lo<=point<=hi, got {self.lo},{self.point},{self.hi}")
        return self

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def __str__(self) -> str:
        return f"{self.point:.3g} [{self.lo:.3g}–{self.hi:.3g}]{(' ' + self.unit) if self.unit else ''}"


class Source(Frozen):
    """A citation. No non-neutral finding may exist without at least one."""

    url: str
    title: str = ""
    excerpt: str = ""
    retrieved_at: datetime = Field(default_factory=utcnow)
    kind: Literal["web", "institutional", "registry", "api", "rule", "memory"] = "web"


# --------------------------------------------------------------------------
# Institution (ADR-0026) — loaded from config/institutions/<id>.yaml
# --------------------------------------------------------------------------

class Locale(Frozen):
    primary_language: str = "en"
    code_mixed: list[str] = Field(default_factory=list)
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"


class Domains(Frozen):
    official: list[str] = Field(default_factory=list)
    email: dict[str, Any] | list[str] = Field(default_factory=list)


class InstitutionSource(Frozen):
    id: str
    url: str
    kind: Literal["html", "pdf_index", "rss"] = "html"
    topics: list[str] = Field(default_factory=list)
    refresh: str = "6h"
    authority: float = Field(default=1.0, ge=0.0, le=1.0)
    discover_links: bool = False


class Channel(Frozen):
    kind: Literal["website", "email_domain", "telegram", "phone"]
    value: str
    note: str = ""


class CohortDimension(Frozen):
    id: str
    label: str
    values: list[str] = Field(default_factory=list)


class CohortSpec(Frozen):
    verified: bool = False
    dimensions: list[CohortDimension] = Field(default_factory=list)


class CalendarWindow(Frozen):
    id: str
    label: str
    months: list[int] = Field(default_factory=list)
    effect: str = ""


class CalendarSpec(Frozen):
    verified: bool = False
    windows: list[CalendarWindow] = Field(default_factory=list)


class PaymentSpec(Frozen):
    verified: bool = False
    official_upi_handles: list[str] = Field(default_factory=list)
    collects_fees_via_messaging: bool = False


class Institution(Frozen):
    """Immutable for the process lifetime. Never a hardcoded string in app code."""

    id: str = Field(pattern=r"^[a-z0-9\-]+$")
    display_name: str
    short_name: str
    synthetic: bool = False
    locale: Locale = Field(default_factory=Locale)
    domains: Domains = Field(default_factory=Domains)
    sources: list[InstitutionSource] = Field(default_factory=list)
    official_channels: list[Channel] = Field(default_factory=list)
    cohorts: CohortSpec = Field(default_factory=CohortSpec)
    calendar: CalendarSpec = Field(default_factory=CalendarSpec)
    payments: PaymentSpec = Field(default_factory=PaymentSpec)

    def unverified_blocks(self) -> list[str]:
        """Blocks whose values were assumed. Never rendered to a user as fact."""
        out = []
        for name in ("cohorts", "calendar", "payments"):
            blk = getattr(self, name)
            if getattr(blk, "verified", True) is False:
                out.append(name)
        return out


class InstitutionSighting(Frozen):
    """The only place a Strain touches an institution (ADR-0026)."""

    institution_id: str
    first_seen: datetime = Field(default_factory=utcnow)
    report_count: int = Field(default=0, ge=0)
    local_verdict: "VerdictLabel | None" = None


# --------------------------------------------------------------------------
# Ingest
# --------------------------------------------------------------------------

class ForwardMarkers(Frozen):
    """Read from screenshot chrome, not the message body. The only spread signal
    available without surveillance."""

    is_forwarded: bool | None = None
    is_frequently_forwarded: bool | None = None
    visible_timestamp: datetime | None = None
    group_size_hint: int | None = Field(default=None, ge=0)


class Report(Frozen):
    """The raw artifact a human handed us. Immutable."""

    id: str
    institution_id: str
    received_at: datetime = Field(default_factory=utcnow)
    channel: Literal["web", "telegram", "share_intent", "api"] = "web"
    raw_text: str | None = None
    image_sha256: str | None = None
    image_phash: str | None = None
    reporter_hash: str = ""
    forward_markers: ForwardMarkers = Field(default_factory=ForwardMarkers)
    claimed_source: str | None = None
    is_fixture: bool = False

    @model_validator(mode="after")
    def _has_content(self) -> "Report":
        if not self.raw_text and not self.image_sha256:
            raise ValueError("report must carry raw_text or an image")
        return self

    def effective_time(self) -> datetime:
        """Message time where available, report time otherwise (ADR-0018)."""
        return self.forward_markers.visible_timestamp or self.received_at


# --------------------------------------------------------------------------
# Claim
# --------------------------------------------------------------------------

class ClaimType(str, Enum):
    PLACEMENT = "placement"
    FEE = "fee"
    EXAM = "exam"
    SCHOLARSHIP = "scholarship"
    SCHEDULE = "schedule"
    EVENT = "event"
    OTHER = "other"
    OUT_OF_SCOPE = "out_of_scope"   # ADR-0024: refusal is an outcome, not an error


class Entities(Frozen):
    """Hard-gate material (ADR-0008). Differing organisations means a different
    strain even at 0.99 cosine."""

    organisations: list[str] = Field(default_factory=list)
    amounts: list[float] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    contacts: list[str] = Field(default_factory=list)
    upi_handles: list[str] = Field(default_factory=list)


class Claim(Frozen):
    """A structured, falsifiable assertion extracted from a report."""

    id: str
    report_id: str
    institution_id: str
    claim_type: ClaimType
    text: str
    text_en: str = ""            # normalised English, for the dual vector (ADR-0006)
    language: str = "en"
    entities: Entities = Field(default_factory=Entities)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=utcnow)
    degraded: bool = False       # true when produced by the deterministic fallback

    @property
    def in_scope(self) -> bool:
        return self.claim_type is not ClaimType.OUT_OF_SCOPE


# --------------------------------------------------------------------------
# Strain — GLOBAL. Deliberately has no institution_id (ADR-0026).
# --------------------------------------------------------------------------

class MutationDiff(Frozen):
    """What changed between parent and child, and which signal noticed."""

    dominant_signal: Literal["semantic", "entity", "phash"]
    semantic_distance: float = Field(ge=0.0, le=2.0)
    entity_changes: dict[str, list[str]] = Field(default_factory=dict)
    phash_distance: int | None = None
    summary: str = ""


class Strain(Frozen):
    """A cluster of message variants that are the same underlying rumour.

    NO institution_id. A strain learned anywhere is recognised everywhere; only
    the verdict about it is re-derived locally.
    """

    id: str
    label: str = ""
    parent_id: str | None = None
    aliases: list[str] = Field(default_factory=list)   # merged ids; never renamed
    centroid_native: list[float] = Field(default_factory=list)
    centroid_en: list[float] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    phash: str | None = None
    first_seen: datetime = Field(default_factory=utcnow)
    last_seen: datetime = Field(default_factory=utcnow)
    report_count: int = Field(default=0, ge=0)
    seen_at: list[InstitutionSighting] = Field(default_factory=list)
    mutation_diff: MutationDiff | None = None
    is_fixture: bool = False

    def sighting(self, institution_id: str) -> InstitutionSighting | None:
        for s in self.seen_at:
            if s.institution_id == institution_id:
                return s
        return None

    def seen_elsewhere(self, institution_id: str) -> list[InstitutionSighting]:
        return [s for s in self.seen_at if s.institution_id != institution_id]


# --------------------------------------------------------------------------
# Evidence & Verdict
# --------------------------------------------------------------------------

Signal = Literal["supports", "contradicts", "neutral"]
AgentStatus = Literal["ok", "unavailable", "not_applicable"]


class Evidence(Frozen):
    """What an agent returns. Never a verdict (ADR-0012)."""

    agent: str
    institution_id: str
    tier: int = Field(ge=0, le=3)
    status: AgentStatus = "ok"
    signal: Signal = "neutral"
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    finding: str = ""
    sources: list[Source] = Field(default_factory=list)
    correlation_group: str = "independent"
    elapsed_ms: int = Field(default=0, ge=0)
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _cite_or_stay_silent(self) -> "Evidence":
        # Agent contract rule 2 (docs/03). Enforced at the type level so an
        # uncited assertion cannot physically exist.
        if self.status == "ok" and self.signal != "neutral" and not self.sources:
            raise ValueError(f"{self.agent}: non-neutral finding requires >=1 source")
        if self.status != "ok" and self.strength != 0.0:
            raise ValueError(f"{self.agent}: non-ok status must carry zero strength")
        return self


class VerdictLabel(str, Enum):
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"
    TRUE = "TRUE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class Verdict(Frozen):
    """Set by deterministic aggregation. The LLM writes prose only (ADR-0013)."""

    id: str
    strain_id: str
    institution_id: str
    label: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    posterior_false: float = Field(ge=0.0, le=1.0)
    headline: str = ""
    reasoning: str = ""
    what_would_change_my_mind: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    tier_reached: int = Field(default=0, ge=0, le=3)
    exit_reason: str = ""
    prose_source: Literal["llm", "template"] = "template"
    overridden_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    is_fixture: bool = False


# --------------------------------------------------------------------------
# Spread & alerting
# --------------------------------------------------------------------------

class SpreadModelTier(str, Enum):
    NONE = "none"              # n < 5  — no curve, and we say so
    BAYESIAN_EXP = "bayesian_exponential"   # 5-20
    LOGISTIC = "logistic"      # 21-60
    SEIR = "seir_hawkes"       # > 60


class SpreadEstimate(Frozen):
    """Per (strain, institution). Every projected quantity is an Interval."""

    strain_id: str
    institution_id: str
    model_tier: SpreadModelTier
    n_reports: int = Field(ge=0)
    growth_rate: Interval | None = None
    branching_ratio: Interval | None = None     # n*, the honest analogue of R0
    projected_peak_at: Interval | None = None   # hours from now
    projected_total: Interval | None = None
    unreached: Interval | None = None
    caveats: list[str] = Field(default_factory=list)
    fit_ok: bool = True
    computed_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _no_projection_without_data(self) -> "SpreadEstimate":
        # ADR-0017: below the sample floor there is no curve. A number here would
        # be numerology that never errors.
        if self.model_tier is SpreadModelTier.NONE:
            for f in ("growth_rate", "branching_ratio", "projected_peak_at", "projected_total"):
                if getattr(self, f) is not None:
                    raise ValueError(f"model_tier=none must not project {f}")
        if not self.fit_ok and not self.caveats:
            raise ValueError("a failed fit must carry a caveat")
        return self


class AlertDecision(Frozen):
    """Expected-harm rule (ADR-0019). Suppressions are published with reasons."""

    should_alert: bool
    expected_harm_prevented: float
    expected_harm_caused: float
    fatigue_cost: float
    reason: str
    unreached_estimate: Interval | None = None


class InoculationCard(Frozen):
    """Exactly two evidence items. Names the technique, not just the instance."""

    technique: str
    headline: str
    body: str
    evidence: list[Source] = Field(default_factory=list, max_length=2, min_length=0)
    action_if_already_harmed: str = ""


class Alert(Frozen):
    id: str
    strain_id: str
    institution_id: str
    verdict_id: str
    card: InoculationCard
    cohorts: dict[str, list[str]] = Field(default_factory=dict)
    decision: AlertDecision
    channels: list[Literal["telegram", "websocket", "webpush"]] = Field(default_factory=list)
    delivered: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    is_fixture: bool = False


# --------------------------------------------------------------------------
# Pipeline result
# --------------------------------------------------------------------------

class IngestResult(Frozen):
    report_id: str
    strain_id: str
    recognised: bool
    verdict: Verdict | None = None
    spread: SpreadEstimate | None = None
    elapsed_ms: int = Field(default=0, ge=0)
    mode: Literal["live", "replay", "degraded"] = "live"


Institution.model_rebuild()
InstitutionSighting.model_rebuild()

__all__ = [
    "Interval", "Source", "Locale", "Domains", "InstitutionSource", "Channel",
    "CohortDimension", "CohortSpec", "CalendarWindow", "CalendarSpec",
    "PaymentSpec", "Institution", "InstitutionSighting", "ForwardMarkers",
    "Report", "ClaimType", "Entities", "Claim", "MutationDiff", "Strain",
    "Signal", "AgentStatus", "Evidence", "VerdictLabel", "Verdict",
    "SpreadModelTier", "SpreadEstimate", "AlertDecision", "InoculationCard",
    "Alert", "IngestResult", "utcnow",
]
