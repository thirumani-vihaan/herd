"""Run one claim through everything that exists today, end to end.

    venv\\Scripts\\python.exe tools\\demo_run.py
    venv\\Scripts\\python.exe tools\\demo_run.py --offline
    venv\\Scripts\\python.exe tools\\demo_run.py --text "your message here"

There is no `app/wiring.py` yet, so this assembles the container by hand. It is
deliberately the smallest honest assembly: perceive -> recognise -> cascade ->
aggregate, with the real agents and the real config. When wiring.py is written,
this file becomes its first caller rather than a second copy of it.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.http import BlockedFetcher, HttpxFetcher  # noqa: E402
from app.config import get_settings, get_thresholds  # noqa: E402
from app.contracts import ForwardMarkers, Strain  # noqa: E402
from app.institution import get_institution, startup_report  # noqa: E402
from app.investigate.aggregate import Aggregator, explain  # noqa: E402
from app.investigate.agents import (ContactForensics, DomainForensics,  # noqa: E402
                                    FraudHeuristics, StrainPrior,
                                    TemplateProvenance, URLSafety)
from app.investigate.cascade import Cascade  # noqa: E402
from app.perceive.extract import deterministic_extract  # noqa: E402
from app.perceive.redact import redact_text  # noqa: E402
from app.storage.sqlite_store import SqliteStore  # noqa: E402

FLAGSHIP = (
    "*TCS Mega Placement Drive 2026*\n"
    "Eligible: VNR VJIET final year, all branches. Package: 12 LPA\n"
    "Limited slots! Register now: bit.ly/tcs-drive26\n"
    "Registration fee Rs 750 payable to hr.tcsdrive@okaxis\n"
    "Contact tcs.hr.official@gmail.com or 9876543210. Last date tonight!"
)


def build_cascade(institution, store, fetcher, markers):
    th = get_thresholds()
    agents = [
        FraudHeuristics(official_domains=set(institution.domains.official or [])),
        TemplateProvenance(markers),
        StrainPrior(store, institution.id),
        DomainForensics(institution, fetcher),
        URLSafety(institution, fetcher),
        ContactForensics(institution, fetcher),
    ]
    return Cascade(
        agents, Aggregator.from_thresholds(th),
        exit_bars={0: th.f("cascade.exit.tier0"), 1: th.f("cascade.exit.tier1"),
                   2: th.f("cascade.exit.tier2")},
        false_exit_multiplier=th.f("cascade.false_exit_multiplier"),
        unverified_exit_multiplier=th.f("cascade.unverified_exit_multiplier"),
        deadline_ms=th.i("cascade.deadline_ms"),
        confirming_agents=set(th.get("verdict.confirming_agents")))


async def main(text: str, offline: bool) -> int:
    settings = get_settings()
    institution = get_institution()

    print("=" * 74)
    for line in startup_report(institution):
        print(line)
    print(f"  mode: {'OFFLINE (network blocked)' if offline else settings.demo_mode}")
    print("=" * 74)

    store = SqliteStore(ROOT / "data" / "demo_run.db")
    await store.init()

    print("\n[1] PERCEIVE")
    redacted, removed = redact_text(text)
    print(f"    redacted {len(removed)} PII item(s): {removed or 'none'}")
    claim = deterministic_extract(redacted, report_id="demo-report",
                                  institution_id=institution.id,
                                  claim_id="demo-claim")
    print(f"    claim_type   : {claim.claim_type.value}")
    print(f"    confidence   : {claim.extraction_confidence:.2f}")
    e = claim.entities
    for name in ("organisations", "amounts", "urls", "domains", "contacts",
                 "upi_handles", "dates"):
        value = getattr(e, name)
        if value:
            print(f"    {name:<13}: {value}")

    print("\n[2] RECOGNISE")
    now = datetime.now(timezone.utc)
    strain = Strain(id="demo-strain", first_seen=now, last_seen=now,
                    report_count=1, entities=claim.entities)
    print(f"    strain       : {strain.id} (new — nothing to match against yet)")

    print("\n[3] INVESTIGATE")
    fetcher = BlockedFetcher() if offline else HttpxFetcher()
    cascade = build_cascade(institution, store, fetcher, ForwardMarkers(
        is_forwarded=True, is_frequently_forwarded=True))
    result = await cascade.run(claim, strain)

    for t in result.trace:
        print(f"    tier {t.tier}  ran={t.agents_run}")
        if t.agents_skipped:
            print(f"            skipped={t.agents_skipped} (not applicable, cost nothing)")
        for ev in t.evidence:
            mark = "!" if ev.signal == "contradicts" else (
                "+" if ev.signal == "supports" else " ")
            status = "" if ev.status == "ok" else f"  [{ev.status}]"
            print(f"      {mark} {ev.agent:<18} {ev.signal:<11} "
                  f"{ev.strength:.2f}{status}  {ev.finding[:70]}")
        print(f"            -> p(false)={t.posterior_after:.3f}  "
              f"label={t.label_after}"
              + (f"  EXIT: {t.exit_reason}" if t.exited else ""))

    agg = result.aggregation
    print("\n[4] AGGREGATE")
    for line in explain(agg.contributions):
        print(f"    {line}")

    print("\n" + "=" * 74)
    print(f"  VERDICT     : {agg.label.value}")
    print(f"  p(false)    : {agg.posterior_false:.3f}")
    print(f"  confidence  : {agg.confidence:.3f}")
    if agg.downgraded_for_lack_of_confirmation:
        print("  note        : not confirmed TRUE — no entitled agent found a source")
    if agg.downgraded_for_insufficient_standing:
        print("  note        : only memory-class evidence — cannot conclude alone")
    print(f"  tiers used  : {result.highest_tier_reached + 1} of 4 "
          f"({result.tiers_skipped} never bought)")
    print(f"  elapsed     : {result.elapsed_ms} ms")
    print("=" * 74)

    if hasattr(fetcher, "aclose"):
        await fetcher.aclose()
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--text", default=FLAGSHIP)
    p.add_argument("--offline", action="store_true")
    a = p.parse_args()
    raise SystemExit(asyncio.run(main(a.text, a.offline)))
