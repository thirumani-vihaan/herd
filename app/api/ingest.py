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
from typing import Annotated

from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from pydantic import BaseModel

from app.contracts import ForwardMarkers, Strain
from app.institution import get_institution
from app.perceive.extract import extract_claim
from app.perceive.redact import redact_text
from app.wiring import build_container, Container

logger = logging.getLogger(__name__)

# Idempotency cache: (hash) -> (tracking_id, timestamp)
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 60.0

# Global container loaded at startup
container: Container | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global container
    inst = get_institution()
    container = build_container(inst.id)
    await container.store.init()
    yield
    if hasattr(container.fetcher, "aclose"):
        await container.fetcher.aclose()


app = FastAPI(lifespan=lifespan)


class IngestResponse(BaseModel):
    tracking_id: str
    status: str
    verdict: str | None = None
    summary: str | None = None


async def process_pipeline(tracking_id: str, text: str, image_bytes: bytes | None, 
                           reporter_hash: str, is_forwarded: bool, is_frequent: bool):
    """Run the actual investigation pipeline."""
    if not container:
        return

    inst = container.institution
    redacted, _ = redact_text(text)
    claim = await extract_claim(
        llm=container.llm,
        text=redacted,
        image_bytes=image_bytes,
        report_id=f"rep_{tracking_id}",
        institution_id=inst.id,
        institution_short_name=inst.short_name,
        claim_id=f"clm_{tracking_id[:12]}"
    )
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    strain = Strain(id=f"str_{tracking_id[:12]}", first_seen=now, last_seen=now,
                    report_count=1, entities=claim.entities)
    
    cascade = container.build_cascade(ForwardMarkers(
        is_forwarded=is_forwarded, is_frequently_forwarded=is_frequent))
    
    result = await cascade.run(claim, strain)
    
    if container.llm.available():
        prose = await container.llm.write_prose(
            label=result.aggregation.label.value,
            evidence=result.evidence,
            claim=claim
        )
        summary = prose.get("summary") or "Investigation complete."
    else:
        summary = "Investigation complete."
    
    payload = {
        "verdict": result.aggregation.label.value,
        "summary": summary
    }

    # Task 8: Deliver via Notifiers
    for notifier in container.notifiers:
        if notifier.available():
            await notifier.send(payload)
            
    return payload


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
    
    # Clean cache
    expired = [k for k, v in _cache.items() if now - v[1] > CACHE_TTL]
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

    tracking_id = uuid.uuid4().hex
    _cache[idemp_key] = (tracking_id, now)

    background_tasks.add_task(
        process_pipeline,
        tracking_id, text, image_bytes, reporter_hash,
        is_forwarded, is_frequently_forwarded
    )

    return IngestResponse(
        tracking_id=tracking_id,
        status="accepted"
    )
