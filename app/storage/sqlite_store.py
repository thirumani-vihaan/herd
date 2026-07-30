"""SQLite persistence (ADR-0022).

Why SQLite and not Postgres: the demo must run with the network cable pulled,
on one laptop, with no service to start. WAL gives us concurrent readers
alongside the single writer, which is exactly our shape — one ingest path, many
dashboard readers.

Why raw sqlite3 and not an ORM: the contracts are already Pydantic models with
validation. An ORM would give us a second, weaker schema that can drift from
the first. Instead every row stores the model's JSON alongside the few columns
we actually query on, so the model stays the single source of truth and the
columns are pure index.

All calls hop to a thread, because sqlite3 is blocking and the ingest path is
async. A single write lock serialises writers so WAL never sees a conflict.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.contracts import Alert, Claim, Report, SpreadEstimate, Strain, Verdict
from app.interfaces import Store

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    institution_id  TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    image_sha256    TEXT,
    image_phash     TEXT,
    reporter_hash   TEXT NOT NULL,
    strain_id       TEXT,
    is_fixture      INTEGER NOT NULL DEFAULT 0,
    doc             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reports_dedupe   ON reports(reporter_hash, image_sha256, received_at);
CREATE INDEX IF NOT EXISTS ix_reports_strain   ON reports(strain_id, institution_id);
CREATE INDEX IF NOT EXISTS ix_reports_inst_time ON reports(institution_id, received_at);

CREATE TABLE IF NOT EXISTS claims (
    id              TEXT PRIMARY KEY,
    report_id       TEXT NOT NULL,
    institution_id  TEXT NOT NULL,
    claim_type      TEXT NOT NULL,
    doc             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_claims_report ON claims(report_id);

-- Strains are global on purpose (ADR-0026). There is no institution_id column
-- here and there must never be one: strain memory is the network effect.
CREATE TABLE IF NOT EXISTS strains (
    id           TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    parent_id    TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    report_count INTEGER NOT NULL DEFAULT 0,
    is_fixture   INTEGER NOT NULL DEFAULT 0,
    doc          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_strains_last_seen ON strains(last_seen DESC);

CREATE TABLE IF NOT EXISTS verdicts (
    id             TEXT PRIMARY KEY,
    strain_id      TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    label          TEXT NOT NULL,
    confidence     REAL NOT NULL,
    created_at     TEXT NOT NULL,
    is_fixture     INTEGER NOT NULL DEFAULT 0,
    doc            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_verdicts_scope ON verdicts(strain_id, institution_id, created_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id             TEXT PRIMARY KEY,
    strain_id      TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    is_fixture     INTEGER NOT NULL DEFAULT 0,
    doc            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_alerts_scope ON alerts(institution_id, created_at DESC);

CREATE TABLE IF NOT EXISTS spread (
    strain_id      TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    computed_at    TEXT NOT NULL,
    doc            TEXT NOT NULL,
    PRIMARY KEY (strain_id, institution_id)
);

-- Per-institution sighting of a global strain. This is the join that lets a
-- strain be shared while the *evidence* stays local (ADR-0026).
CREATE TABLE IF NOT EXISTS sightings (
    strain_id      TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    first_seen     TEXT NOT NULL,
    report_count   INTEGER NOT NULL DEFAULT 0,
    local_verdict  TEXT,
    PRIMARY KEY (strain_id, institution_id)
);

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_id TEXT NOT NULL,
    kind           TEXT NOT NULL,
    at             TEXT NOT NULL,
    doc            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_time ON events(institution_id, at DESC);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqliteStore(Store):
    """The only thing that touches the database file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._write_lock = asyncio.Lock()

    # -- lifecycle ---------------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because asyncio.to_thread hands us a pool
        # thread; the write lock is what actually provides safety.
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SqliteStore.init() was never awaited")
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    async def _write(self, sql: str, params: tuple) -> None:
        async with self._write_lock:
            await asyncio.to_thread(self._exec_commit, sql, params)

    def _exec_commit(self, sql: str, params: tuple) -> None:
        self.conn.execute(sql, params)
        self.conn.commit()

    async def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return await asyncio.to_thread(lambda: self.conn.execute(sql, params).fetchall())

    # -- reports -----------------------------------------------------------

    async def save_report(self, report: Report) -> None:
        await self._write(
            "INSERT OR REPLACE INTO reports"
            " (id, institution_id, received_at, image_sha256, image_phash,"
            "  reporter_hash, strain_id, is_fixture, doc)"
            " VALUES (?,?,?,?,?,?,COALESCE((SELECT strain_id FROM reports WHERE id=?),NULL),?,?)",
            (report.id, report.institution_id, _iso(report.received_at),
             report.image_sha256, report.image_phash, report.reporter_hash,
             report.id, int(report.is_fixture), report.model_dump_json()),
        )

    async def recent_duplicate(self, image_sha256: str | None, reporter_hash: str,
                               within_seconds: int) -> str | None:
        """Idempotency, and it runs BEFORE the spread model sees the report.

        A reporter who taps send twice must not become two data points — the
        spread model would read that as growth and the alert threshold is
        partly a function of growth. Deduping after the model would mean a
        double-tap could manufacture an alert.
        """
        cutoff = _iso(_now() - timedelta(seconds=within_seconds))
        if image_sha256:
            rows = await self._rows(
                "SELECT id FROM reports WHERE reporter_hash=? AND image_sha256=?"
                " AND received_at >= ? ORDER BY received_at DESC LIMIT 1",
                (reporter_hash, image_sha256, cutoff),
            )
        else:
            rows = await self._rows(
                "SELECT id FROM reports WHERE reporter_hash=? AND image_sha256 IS NULL"
                " AND received_at >= ? ORDER BY received_at DESC LIMIT 1",
                (reporter_hash, cutoff),
            )
        return rows[0]["id"] if rows else None

    async def link_report_to_strain(self, report_id: str, strain_id: str) -> None:
        await self._write("UPDATE reports SET strain_id=? WHERE id=?", (strain_id, report_id))

    async def reports_for_strain(self, strain_id: str, institution_id: str) -> list[Report]:
        """Scoped to one institution by construction.

        There is no unscoped variant of this method, and that is the point:
        ADR-0026 says institutional evidence never crosses a tenant boundary,
        so the API simply does not offer a way to ask.
        """
        rows = await self._rows(
            "SELECT doc FROM reports WHERE strain_id=? AND institution_id=?"
            " ORDER BY received_at ASC", (strain_id, institution_id))
        return [Report.model_validate_json(r["doc"]) for r in rows]

    async def report_count_for_strain(self, strain_id: str, institution_id: str) -> int:
        rows = await self._rows(
            "SELECT COUNT(*) AS n FROM reports WHERE strain_id=? AND institution_id=?",
            (strain_id, institution_id))
        return int(rows[0]["n"])

    async def recent_reports(self, institution_id: str, hours: float, limit: int = 500) -> list[Report]:
        cutoff = _iso(_now() - timedelta(hours=hours))
        rows = await self._rows(
            "SELECT doc FROM reports WHERE institution_id=? AND received_at >= ?"
            " ORDER BY received_at DESC LIMIT ?", (institution_id, cutoff, limit))
        return [Report.model_validate_json(r["doc"]) for r in rows]

    # -- claims ------------------------------------------------------------

    async def save_claim(self, claim: Claim) -> None:
        await self._write(
            "INSERT OR REPLACE INTO claims (id, report_id, institution_id, claim_type, doc)"
            " VALUES (?,?,?,?,?)",
            (claim.id, claim.report_id, claim.institution_id,
             claim.claim_type.value, claim.model_dump_json()),
        )

    async def claim_for_report(self, report_id: str) -> Claim | None:
        rows = await self._rows("SELECT doc FROM claims WHERE report_id=? LIMIT 1", (report_id,))
        return Claim.model_validate_json(rows[0]["doc"]) if rows else None

    # -- strains (global) --------------------------------------------------

    async def upsert_strain(self, strain: Strain) -> None:
        await self._write(
            "INSERT OR REPLACE INTO strains"
            " (id, label, parent_id, first_seen, last_seen, report_count, is_fixture, doc)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (strain.id, strain.label, strain.parent_id, _iso(strain.first_seen),
             _iso(strain.last_seen), strain.report_count, int(strain.is_fixture),
             strain.model_dump_json()),
        )

    async def get_strain(self, strain_id: str) -> Strain | None:
        rows = await self._rows("SELECT doc FROM strains WHERE id=?", (strain_id,))
        return Strain.model_validate_json(rows[0]["doc"]) if rows else None

    async def all_strains(self) -> list[Strain]:
        rows = await self._rows("SELECT doc FROM strains ORDER BY last_seen DESC")
        return [Strain.model_validate_json(r["doc"]) for r in rows]

    # -- sightings (the scoped half of ADR-0026) ---------------------------

    async def record_sighting(self, strain_id: str, institution_id: str,
                              at: datetime | None = None) -> None:
        at = at or _now()
        await self._write(
            "INSERT INTO sightings (strain_id, institution_id, first_seen, report_count)"
            " VALUES (?,?,?,1)"
            " ON CONFLICT(strain_id, institution_id)"
            " DO UPDATE SET report_count = report_count + 1",
            (strain_id, institution_id, _iso(at)),
        )

    async def sightings_for_strain(self, strain_id: str) -> list[dict[str, Any]]:
        """Which institutions have seen this strain.

        Deliberately returns only counts and dates — never report text, never
        evidence. This is the exact width of the cross-institution channel, and
        it is narrow enough that it cannot manufacture a verdict on its own.
        """
        rows = await self._rows(
            "SELECT institution_id, first_seen, report_count, local_verdict"
            " FROM sightings WHERE strain_id=? ORDER BY first_seen ASC", (strain_id,))
        return [dict(r) for r in rows]

    async def set_sighting_verdict(self, strain_id: str, institution_id: str, label: str) -> None:
        await self._write(
            "UPDATE sightings SET local_verdict=? WHERE strain_id=? AND institution_id=?",
            (label, strain_id, institution_id))

    # -- verdicts ----------------------------------------------------------

    async def save_verdict(self, verdict: Verdict) -> None:
        await self._write(
            "INSERT OR REPLACE INTO verdicts"
            " (id, strain_id, institution_id, label, confidence, created_at, is_fixture, doc)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (verdict.id, verdict.strain_id, verdict.institution_id, verdict.label.value,
             verdict.confidence, _iso(verdict.created_at), int(verdict.is_fixture),
             verdict.model_dump_json()),
        )

    async def get_verdict(self, strain_id: str, institution_id: str) -> Verdict | None:
        rows = await self._rows(
            "SELECT doc FROM verdicts WHERE strain_id=? AND institution_id=?"
            " ORDER BY created_at DESC LIMIT 1", (strain_id, institution_id))
        return Verdict.model_validate_json(rows[0]["doc"]) if rows else None

    async def recent_verdicts(self, institution_id: str, limit: int = 50) -> list[Verdict]:
        rows = await self._rows(
            "SELECT doc FROM verdicts WHERE institution_id=?"
            " ORDER BY created_at DESC LIMIT ?", (institution_id, limit))
        return [Verdict.model_validate_json(r["doc"]) for r in rows]

    # -- alerts ------------------------------------------------------------

    async def save_alert(self, alert: Alert) -> None:
        await self._write(
            "INSERT OR REPLACE INTO alerts"
            " (id, strain_id, institution_id, created_at, is_fixture, doc) VALUES (?,?,?,?,?,?)",
            (alert.id, alert.strain_id, alert.institution_id, _iso(alert.created_at),
             int(alert.is_fixture), alert.model_dump_json()),
        )

    async def alerts_since(self, institution_id: str, hours: float) -> list[Alert]:
        cutoff = _iso(_now() - timedelta(hours=hours))
        rows = await self._rows(
            "SELECT doc FROM alerts WHERE institution_id=? AND created_at >= ?"
            " ORDER BY created_at DESC", (institution_id, cutoff))
        return [Alert.model_validate_json(r["doc"]) for r in rows]

    # -- spread ------------------------------------------------------------

    async def save_spread(self, est: SpreadEstimate) -> None:
        await self._write(
            "INSERT OR REPLACE INTO spread (strain_id, institution_id, computed_at, doc)"
            " VALUES (?,?,?,?)",
            (est.strain_id, est.institution_id, _iso(est.computed_at), est.model_dump_json()),
        )

    async def get_spread(self, strain_id: str, institution_id: str) -> SpreadEstimate | None:
        rows = await self._rows(
            "SELECT doc FROM spread WHERE strain_id=? AND institution_id=?",
            (strain_id, institution_id))
        return SpreadEstimate.model_validate_json(rows[0]["doc"]) if rows else None

    # -- events (for /metrics/herd and the live feed) ----------------------

    async def append_event(self, institution_id: str, kind: str, payload: dict[str, Any]) -> None:
        await self._write(
            "INSERT INTO events (institution_id, kind, at, doc) VALUES (?,?,?,?)",
            (institution_id, kind, _iso(_now()), json.dumps(payload, default=str)),
        )

    async def events_since(self, institution_id: str, hours: float, limit: int = 200
                           ) -> list[dict[str, Any]]:
        cutoff = _iso(_now() - timedelta(hours=hours))
        rows = await self._rows(
            "SELECT kind, at, doc FROM events WHERE institution_id=? AND at >= ?"
            " ORDER BY at DESC LIMIT ?", (institution_id, cutoff, limit))
        return [{"kind": r["kind"], "at": r["at"], **json.loads(r["doc"])} for r in rows]

    # -- reset (fixtures only) --------------------------------------------

    async def purge_fixtures(self) -> int:
        """Remove seeded rows without touching anything a live demo produced.

        Every seeded row carries is_fixture=True precisely so this can exist;
        a demo that cannot be reset cleanly gets rehearsed once and then rots.
        """
        async with self._write_lock:
            def run() -> int:
                n = 0
                for table in ("reports", "claims", "strains", "verdicts", "alerts"):
                    n += self.conn.execute(f"DELETE FROM {table} WHERE is_fixture=1").rowcount
                self.conn.execute("DELETE FROM sightings")
                self.conn.execute("DELETE FROM spread")
                self.conn.commit()
                return n
            return await asyncio.to_thread(run)
