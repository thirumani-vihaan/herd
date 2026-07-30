"""Telemetry. Every hop between 'report received' and 'verdict rendered' gets a
named timer.

Partial instrumentation is worse than none: it produces a confident latency
number that quietly omits whichever hop nobody measured.
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

import structlog

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

STAGES = (
    "ingest", "redact", "extract", "embed", "match", "investigate",
    "aggregate", "prose", "spread", "alert", "persist",
)


@dataclass
class Trace:
    """Per-request stage timings. Attached to the response, streamed to the UI."""

    request_id: str
    stages: dict[str, float] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            ms = (time.perf_counter() - t0) * 1000.0
            self.stages[name] = self.stages.get(name, 0.0) + ms

    def event(self, kind: str, **data: Any) -> None:
        self.events.append({"t": kind, "at_ms": round(self.elapsed_ms, 1), **data})

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000.0

    def summary(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "total_ms": round(self.elapsed_ms, 1),
            "stages": {k: round(v, 1) for k, v in self.stages.items()},
        }

    def unmeasured(self) -> list[str]:
        """Stages that ran in this request path but recorded no time.

        Used by the latency gate: a budget assertion that silently omits a hop is
        not an assertion.
        """
        return [s for s in self.stages if self.stages[s] == 0.0]


def set_request_id(rid: str) -> None:
    _request_id.set(rid)


def get_request_id() -> str:
    return _request_id.get()


def _add_request_id(_logger, _name, event_dict):
    event_dict["rid"] = _request_id.get()
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout,
                        level=getattr(logging, level.upper(), logging.INFO))
    processors = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
    ]
    processors.append(
        structlog.processors.JSONRenderer() if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "herd"):
    return structlog.get_logger(name)
