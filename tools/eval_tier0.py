"""Does Tier 0 alone get the demo right? Answer with numbers, not hope.

Tier 0 is free, offline and ~30 ms. The claim in the pitch is that it settles
the majority of reports without spending a paisa. That claim is either true on
the labelled corpus or it is marketing, so measure it before believing it.

    venv\\Scripts\\python.exe tools\\eval_tier0.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_thresholds  # noqa: E402
from app.contracts import (Claim, Evidence, ForwardMarkers, Report, Strain,  # noqa: E402
                           VerdictLabel)
from app.investigate.aggregate import Aggregator, explain  # noqa: E402
from app.investigate.agents import FraudHeuristics, TemplateProvenance  # noqa: E402
from app.perceive.extract import deterministic_extract  # noqa: E402
from app.perceive.redact import redact_text  # noqa: E402


def build_aggregator() -> Aggregator:
    return Aggregator.from_thresholds(get_thresholds())


def stub_strain(claim: Claim, report_count: int = 1) -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id=f"strain-{claim.id}", first_seen=now, last_seen=now,
                  report_count=report_count, seen_at=[], entities=claim.entities)


async def evaluate() -> int:
    rows = [json.loads(l) for l in
            (ROOT / "fixtures" / "labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    aggregator = build_aggregator()
    agg_cfg = get_thresholds().get("aggregation")

    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[str] = []
    total_ms = 0.0

    for row in rows:
        inst = "fixture-inst"
        red, _ = redact_text(row["text"])
        claim = deterministic_extract(
            red, report_id=row["id"], institution_id=inst,
            claim_id="claim-" + row["id"])

        markers = ForwardMarkers(is_forwarded=row.get("forwarded"),
                                 is_frequently_forwarded=row.get("frequently_forwarded"))
        official = {row["institution_domain"]} if row.get("institution_domain") else set()

        agents = [FraudHeuristics(official_domains=official,
                                  correlated_discount=agg_cfg["correlated_discount"],
                                  saturation=agg_cfg["agent_saturation"]),
                  TemplateProvenance(markers)]
        strain = stub_strain(claim, report_count=1)

        evidence: list[Evidence] = []
        for a in agents:
            if a.applies_to(claim):
                ev = await a.run(claim, strain)
                evidence.append(ev)
                total_ms += ev.elapsed_ms

        result = aggregator.aggregate(evidence)
        got = result.label.value
        want = row["truth"]
        confusion[(want, got)] += 1

        if not _acceptable(want, got):
            misses.append(
                f"  {row['id']:<28} want={want:<12} got={got:<12} "
                f"p={result.posterior_false:.3f}\n"
                + "".join(f"      {line}\n" for line in explain(result.contributions)))

    print("=" * 72)
    print("TIER-0 ONLY  (FraudHeuristics + TemplateProvenance, no network)")
    print("=" * 72)
    labels = ["TRUE", "MISLEADING", "FALSE", "UNVERIFIED", "OUT_OF_SCOPE"]
    header = "truth \\ got"
    print(f"{header:<14}" + "".join(f"{l:<13}" for l in labels))
    for want in labels:
        row_counts = "".join(f"{confusion[(want, got)]:<13}" for got in labels)
        if any(confusion[(want, g)] for g in labels):
            print(f"{want:<14}{row_counts}")

    n = len(rows)
    exact = sum(c for (w, g), c in confusion.items() if w == g)
    ok = sum(c for (w, g), c in confusion.items() if _acceptable(w, g))
    harmful = sum(c for (w, g), c in confusion.items()
                  if w == "TRUE" and g in ("FALSE", "MISLEADING"))

    print()
    print(f"exact label match : {exact}/{n} = {exact / n:.0%}")
    print(f"acceptable        : {ok}/{n} = {ok / n:.0%}   (abstaining is acceptable)")
    print(f"HARMFUL (true->false accusation): {harmful}")
    print(f"mean tier-0 latency: {total_ms / n:.1f} ms per claim")

    if misses:
        print("\nnot acceptable:")
        print("".join(misses))

    # A false accusation of a genuine notice is the one failure mode that
    # destroys the product's reason to exist. Nothing else here is fatal.
    return 1 if harmful else 0


def _acceptable(want: str, got: str) -> bool:
    """Tier 0 is allowed to abstain; it is not allowed to be confidently wrong."""
    if want == got:
        return True
    if got == "UNVERIFIED":
        return True                      # honest abstention, Tier 1+ will decide
    if want == "OUT_OF_SCOPE":
        return got in ("TRUE", "UNVERIFIED")
    if want == "FALSE" and got == "MISLEADING":
        return True                      # right direction, less certain
    if want == "MISLEADING" and got == "FALSE":
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(asyncio.run(evaluate()))
