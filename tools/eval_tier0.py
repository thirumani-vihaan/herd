"""Does Tier 0 alone get the demo right? Answer with numbers, not hope.

Tier 0 is free, offline and ~30 ms. The claim in the pitch is that it settles
the majority of reports without spending a paisa. That claim is either true on
the labelled corpus or it is marketing, so measure it before believing it.

    venv\\Scripts\\python.exe tools\\eval_tier0.py
    venv\\Scripts\\python.exe tools\\eval_tier0.py --with-tier1

`--with-tier1` adds the Tier-1 agents *with the network blocked*, which is the
configuration the demo has to survive. It measures the half of Tier 1 that is
pure string reasoning — domain impersonation, lookalikes, contact and payment
mismatch — and deliberately gives no credit for RDAP or Safe Browsing, so the
number it prints is a floor rather than a best case.
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
from app.contracts import (Claim, Domains, Evidence, ForwardMarkers,  # noqa: E402
                           Institution, PaymentSpec, Report, Strain, VerdictLabel)
from app.investigate.aggregate import Aggregator, explain  # noqa: E402
from app.investigate.agents import (ContactForensics, DomainForensics,  # noqa: E402
                                    FraudHeuristics, TemplateProvenance, URLSafety)
from app.investigate.agents._common import label_of  # noqa: E402
from app.perceive.extract import deterministic_extract  # noqa: E402
from app.perceive.redact import redact_text  # noqa: E402


class _Blocked:
    """The network, unplugged. Every Tier-1 agent must survive this."""

    async def get_json(self, *a, **k): raise ConnectionError("network blocked")
    async def get_text(self, *a, **k): raise ConnectionError("network blocked")
    async def post_json(self, *a, **k): raise ConnectionError("network blocked")


def build_aggregator() -> Aggregator:
    return Aggregator.from_thresholds(get_thresholds())


def stub_strain(claim: Claim, report_count: int = 1) -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id=f"strain-{claim.id}", first_seen=now, last_seen=now,
                  report_count=report_count, seen_at=[], entities=claim.entities)


def stub_institution(domain: str | None) -> Institution:
    """A profile synthesised from the fixture's own institution domain.

    The corpus is deliberately not tied to one college, so this builds the
    profile each row implies. Payments stay unverified, which means the UPI
    check abstains — the honest setting when nobody has published the official
    handles.
    """
    label = label_of(domain) if domain else "fixture"
    return Institution(
        id="fixture-inst", display_name=label or "fixture",
        short_name=label or "fixture",
        domains=Domains(official=[domain] if domain else [],
                        email=[domain] if domain else []),
        payments=PaymentSpec(verified=False))


async def evaluate(with_tier1: bool = False) -> int:
    rows = [json.loads(l) for l in
            (ROOT / "fixtures" / "labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    aggregator = build_aggregator()
    agg_cfg = get_thresholds().get("aggregation")

    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[str] = []
    total_ms = 0.0
    tier1_spoke: Counter[str] = Counter()
    tier1_seen: set[str] = set()

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
        if with_tier1:
            profile = stub_institution(row.get("institution_domain"))
            blocked = _Blocked()
            agents += [DomainForensics(profile, blocked),
                       URLSafety(profile, blocked),
                       ContactForensics(profile, blocked)]
        strain = stub_strain(claim, report_count=1)

        evidence: list[Evidence] = []
        for a in agents:
            if a.applies_to(claim):
                ev = await a.run(claim, strain)
                evidence.append(ev)
                total_ms += ev.elapsed_ms
                if ev.tier == 1:
                    tier1_seen.add(a.name)
                    if ev.signal != "neutral" and ev.status == "ok":
                        tier1_spoke[a.name] += 1

        result = aggregator.aggregate(evidence)
        got = result.label.value
        want = row["truth"]
        confusion[(want, got)] += 1

        if not _acceptable(want, got):
            misses.append(
                f"  {row['id']:<28} want={want:<12} got={got:<12} "
                f"p={result.posterior_false:.3f}\n"
                + "".join(f"      {line}\n" for line in explain(result.contributions)))

    title = ("TIER 0 + TIER 1, NETWORK BLOCKED" if with_tier1
             else "TIER-0 ONLY  (FraudHeuristics + TemplateProvenance, no network)")
    print("=" * 72)
    print(title)
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
    print(f"mean offline latency: {total_ms / n:.1f} ms per claim")

    if misses:
        print("\nnot acceptable:")
        print("".join(misses))

    if with_tier1:
        # An agent that never speaks is indistinguishable from an agent that is
        # switched off, and both look identical in a confusion matrix. Say which
        # ones actually contributed, so a silent agent is a visible fact rather
        # than a number nobody questioned.
        print("\ntier-1 contribution (offline half only):")
        for name in sorted(tier1_seen):
            spoke = tier1_spoke[name]
            note = "" if spoke else "   <- silent on this corpus"
            print(f"  {name:<18} spoke on {spoke}/{n} claims{note}")
        if not sum(tier1_spoke.values()):
            print("  NOTE: the corpus contains no lookalike or impersonating "
                  "domain, so Tier 1's offline half has nothing to find here.")
            print("  That is a gap in the FIXTURES, not evidence that Tier 1 "
                  "works: domain impersonation is the most common real campus")
            print("  scam shape and it is currently unrepresented.")

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
    raise SystemExit(asyncio.run(evaluate("--with-tier1" in sys.argv)))
