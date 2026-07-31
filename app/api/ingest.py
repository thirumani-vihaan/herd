"""Ingest API for receiving screenshots and texts.

Enforces 60s idempotency via image_sha256 and reporter_hash.
Runs the pipeline asynchronously or synchronously based on load.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, UploadFile, Form, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.contracts import ForwardMarkers, Report, Strain
from app.institution import get_institution
from app.perceive.extract import extract_claim
from app.perceive.redact import redact_text
from app.spread.velocity import calculate_velocity
from app.wiring import build_container, Container
from app.config import get_thresholds

logger = logging.getLogger(__name__)

# Idempotency cache: (hash) -> (tracking_id, timestamp)
_cache: dict[str, tuple[str, float]] = {}

# Global container loaded at startup
container: Container | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global container
    inst = get_institution()
    container = build_container(inst.id)
    await container.store.init()
    # Warm the embedding model at startup. Loading it lazily on the first
    # request cost ~40s, which is the first thing a demo audience would see.
    try:
        await asyncio.to_thread(container.embeddings.encode, ["warmup"])
        logger.info("embedding model warmed")
    except Exception as exc:
        logger.warning("embedding warm-up skipped: %s", exc)
    yield
    if hasattr(container.fetcher, "aclose"):
        await container.fetcher.aclose()


app = FastAPI(lifespan=lifespan)

# Allow CORS for UI dev
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


class IngestResponse(BaseModel):
    tracking_id: str
    status: str
    verdict: str | None = None
    summary: str | None = None
    result: dict[str, Any] | None = None


def _serialise(result: Any, claim: Any, strain: Any, velocity: str,
               report_count: int, summary: str) -> dict[str, Any]:
    """Everything the interface needs to show its work.

    A wrapper can only show an answer. This exposes the machinery: which agents
    ran, what each one found and cited, how long it took, how belief moved tier
    by tier, and which tiers the cascade never had to buy.
    """
    agg = result.aggregation
    th = get_thresholds()
    return {
        "verdict": agg.label.value,
        "summary": summary,
        "bands": th.get("verdict.bands"),
        "posterior_false": round(agg.posterior_false, 4),
        "prior": round(agg.prior, 4),
        "confidence": round(getattr(agg, "confidence", 0.0) or 0.0, 4),
        "clamped": bool(agg.clamped),
        "withheld_confirmation": bool(agg.downgraded_for_lack_of_confirmation),
        "withheld_for_standing": bool(agg.downgraded_for_insufficient_standing),
        "elapsed_ms": result.elapsed_ms,
        "deadline_exceeded": result.deadline_exceeded,
        "highest_tier_reached": result.highest_tier_reached,
        "tiers_skipped": result.tiers_skipped,
        "claim": {
            "text": claim.text,
            "type": claim.claim_type.value,
            "language": claim.language,
            "degraded": bool(getattr(claim, "degraded", False)),
        },
        "strain": {
            "id": strain.id,
            "report_count": report_count,
            "velocity": velocity,
            "first_seen": strain.first_seen.isoformat() if strain.first_seen else None,
        },
        "trace": [
            {
                "tier": t.tier,
                "agents_run": list(t.agents_run),
                "agents_skipped": list(t.agents_skipped),
                "elapsed_ms": t.elapsed_ms,
                "posterior_after": round(t.posterior_after, 4),
                "label_after": t.label_after,
                "exited": t.exited,
            }
            for t in result.trace
        ],
        "evidence": [
            {
                "agent": e.agent,
                "tier": e.tier,
                "status": e.status,
                "signal": e.signal,
                "strength": round(e.strength, 4),
                "finding": e.finding,
                "elapsed_ms": e.elapsed_ms,
                "error": e.error,
                "sources": [
                    {"url": s.url, "title": s.title,
                     "excerpt": s.excerpt, "kind": s.kind}
                    for s in e.sources
                ],
            }
            for e in result.evidence
        ],
    }


async def process_pipeline(tracking_id: str, text: str, image_bytes: bytes | None, 
                           reporter_hash: str, is_forwarded: bool, is_frequent: bool,
                           image_sha256: str = ""):
    """Run the actual investigation pipeline."""
    if not container:
        return

    inst = container.institution
    redacted, _ = redact_text(text)
    markers = ForwardMarkers(is_forwarded=is_forwarded,
                             is_frequently_forwarded=is_frequent)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Persist the report first, so the strain memory and the velocity signal are
    # both computed from data that actually exists (never fabricated).
    report = Report(
        id=f"rep_{tracking_id}", institution_id=inst.id, received_at=now,
        channel="web", raw_text=redacted, image_sha256=image_sha256 or None,
        reporter_hash=reporter_hash or "anonymous", forward_markers=markers,
    )
    await container.store.save_report(report)

    claim = await extract_claim(
        llm=container.llm,
        text=redacted,
        image_bytes=image_bytes,
        report_id=report.id,
        institution_id=inst.id,
        institution_short_name=inst.short_name,
        claim_id=f"clm_{tracking_id[:12]}"
    )
    await container.store.save_claim(claim)

    # Real strain assignment (ADR-0007) rather than a fresh single-report strain,
    # so StrainPrior sees genuine history and repeat reports accumulate.
    # assign() only recognises; commit() folds the report into the centroid and
    # re-indexes it, which is what makes the *next* report match this one.
    assignment = await container.strain_engine.assign(
        claim, image_sha256=image_sha256 or None)
    native, en = container.strain_engine.embed_pair(claim)
    strain = container.strain_engine.commit(assignment.strain, claim, native, en)
    await container.store.upsert_strain(strain)
    await container.store.link_report_to_strain(report.id, strain.id)

    cascade = container.build_cascade(markers)
    result = await cascade.run(claim, strain)

    summary = ""
    if container.llm.available():
        prose = await container.llm.write_prose(
            label=result.aggregation.label.value,
            evidence=result.evidence,
            claim=claim
        )
        summary = (prose.get("summary") or "").strip()
    if not summary:
        summary = _fallback_summary(result)

    # Velocity from the real report timestamps for this strain (ADR-0017: never
    # project from data we do not have).
    reports = await container.store.reports_for_strain(strain.id, inst.id)
    timestamps = [r.received_at for r in reports if r.received_at] or [now]
    velocity = calculate_velocity(timestamps, now)

    payload: dict[str, Any] = _serialise(
        result, claim, strain, velocity, len(timestamps), summary)
    payload["tracking_id"] = tracking_id

    if result.aggregation.label.value in ("FALSE", "MISLEADING"):
        from app.intervene.delivery import generate_inoculation_card
        payload["inoculation_html"] = generate_inoculation_card(
            result.aggregation.label.value, summary, now.strftime("%Y-%m-%d")
        )

    # Task 8: Deliver via Notifiers
    for notifier in container.notifiers:
        if notifier.available():
            await notifier.send(payload)
            
    # Also broadcast to active WebSocket dashboard
    await manager.broadcast(payload)
            
    return payload


def _fallback_summary(result: Any) -> str:
    """Say what the evidence actually was when no prose model is available.

    The previous static string ("Investigation complete.") told the reader
    nothing and hid the fact that prose generation had failed.
    """
    spoke = [e for e in result.evidence
             if e.status == "ok" and e.signal != "neutral"]
    if not spoke:
        return ("No agent found anything decisive, so no claim is being made "
                "about this message.")
    top = sorted(spoke, key=lambda e: e.strength, reverse=True)[:2]
    reasons = "; ".join(e.finding for e in top)
    return f"{result.aggregation.label.value}: {reasons}"


@app.get("/context")
async def context():
    """What the interface needs to know about the active institution.

    The frontend must never contain an institutional string (ADR-0026), and
    that includes its demo samples. They are templated here, from the profile,
    so pointing HERD at a different campus changes the samples too.
    """
    if not container:
        raise HTTPException(status_code=503, detail="service is still starting")

    inst = container.institution
    name = inst.short_name
    official = inst.domains.official[0] if inst.domains.official else "example.edu"
    lookalike = f"{inst.id}-placements.online"
    currency = inst.locale.currency

    return {
        "institution": {
            "id": inst.id,
            "short_name": name,
            "display_name": inst.display_name,
            "official_domain": official,
        },
        "agent_count": sum(
            len(v) for v in container.build_cascade(ForwardMarkers()).tiers.values()
        ),
        "samples": [
            {
                "label": "Fee scam",
                "forwarded": True,
                "text": (
                    f"URGENT: Your {name} exam hall ticket has been blocked due to a "
                    f"pending fee. Pay {currency} 2500 immediately to UPI "
                    f"{inst.id}.fees@okaxis within 2 hours or your registration will "
                    f"be cancelled. Contact 9876543210."
                ),
            },
            {
                "label": "Fake placement",
                "forwarded": True,
                "text": (
                    f"TCS is conducting an off-campus drive exclusively for {name} "
                    f"students. Registration fee {currency} 750. Limited seats. "
                    f"Register at {lookalike} before tonight."
                ),
            },
            {
                "label": "Ordinary notice",
                "forwarded": False,
                "text": (
                    "The placement training session for final year students will be "
                    "held on Friday at 10:00 AM in the seminar hall. Attendance is "
                    "mandatory."
                ),
            },
        ],
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_report(
    background_tasks: BackgroundTasks,
    text: Annotated[str, Form()] = "",
    reporter_hash: Annotated[str, Form()] = "",
    is_forwarded: Annotated[bool, Form()] = False,
    is_frequently_forwarded: Annotated[bool, Form()] = False,
    image: UploadFile | None = None,
):
    now = time.time()

    if not text.strip() and image is None:
        raise HTTPException(
            status_code=400,
            detail="a report must carry text or an image",
        )

    # Clean cache
    cache_ttl = float(get_thresholds().i("ingest.idempotency_window_s"))
    expired = [k for k, v in _cache.items() if now - v[1] > cache_ttl]
    for k in expired:
        del _cache[k]

    image_bytes = None
    image_sha256 = ""
    if image:
        image_bytes = await image.read()
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()

    # Idempotency key
    key_str = f"{reporter_hash}:{image_sha256}:{hashlib.sha256(text.encode()).hexdigest()}"
    idemp_key = hashlib.sha256(key_str.encode()).hexdigest()

    if idemp_key in _cache:
        cached_id, _ = _cache[idemp_key]
        return IngestResponse(
            tracking_id=cached_id,
            status="duplicate_received",
        )

    # Contract path (Store.recent_duplicate): must run BEFORE the spread model
    # sees the report, so a re-send never inflates the velocity signal.
    if container is not None:
        try:
            prior = await container.store.recent_duplicate(
                image_sha256 or None, reporter_hash or "anonymous", int(cache_ttl))
            if prior:
                return IngestResponse(tracking_id=prior, status="duplicate_received")
        except Exception as exc:
            logger.warning("store idempotency check unavailable: %s", exc)

    tracking_id = uuid.uuid4().hex
    _cache[idemp_key] = (tracking_id, now)

    # Run inline. Warm latency is well under two seconds, and a caller that
    # gets the finished investigation back can render it without guessing when
    # a background task landed.
    try:
        payload = await process_pipeline(
            tracking_id, text, image_bytes, reporter_hash,
            is_forwarded, is_frequently_forwarded, image_sha256
        )
    except Exception as exc:
        # A failed investigation must not be cached as a successful one, or a
        # retry of the same message would return the failure forever.
        _cache.pop(idemp_key, None)
        logger.exception("investigation failed for %s", tracking_id)
        raise HTTPException(
            status_code=503,
            detail=f"the investigation could not be completed: {exc}",
        ) from exc

    if isinstance(payload, dict):
        return IngestResponse(
            tracking_id=tracking_id,
            status="accepted",
            verdict=payload.get("verdict"),
            summary=payload.get("summary"),
            result=payload,
        )

    return IngestResponse(
        tracking_id=tracking_id,
        status="accepted"
    )
@app.post("/override/{strain_id}")
async def override_verdict(
    strain_id: str,
    label: str,
    secret: str,
    req: Request
):
    if secret != "admin_secret":
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    container: AppContainer = req.app.state.container
    institution_id = container.config.institution_id
    
    await container.store.override_verdict(
        strain_id=strain_id, 
        institution_id=institution_id, 
        label=label, 
        overridden_by="human_override"
    )
    
    # Broadcast the updated verdict
    v = await container.store.get_verdict(strain_id, institution_id)
    if v:
        strain = await container.store.get_strain(strain_id)
        payload = {
            "verdict": v.label.value,
            "claim": {"text": "VERDICT OVERRIDDEN BY ADMIN"},
            "strain": {
                "id": strain.id if strain else strain_id,
                "report_count": strain.report_count if strain else 0,
                "velocity": getattr(strain, "velocity", 0.0)
            },
            "overridden": True
        }
        manager = req.app.state.ws_manager
        await manager.broadcast(payload)
        
    return {"status": "ok"}
