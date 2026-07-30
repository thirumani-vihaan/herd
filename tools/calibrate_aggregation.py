"""Calibrate the two aggregation constants against the labelled corpus (T044b).

`log_odds_per_unit_strength` and `agent_saturation` were introduced to fix a
real bug — strength was being read as a log-odds delta, which made the whole
evidence system arithmetically incapable of reaching a verdict. Fixing the bug
required two new numbers, and two new numbers I picked by eye are just a nicer
kind of guess. This searches them.

The objective is deliberately not accuracy:

  1. HARD CONSTRAINT: zero genuine notices labelled FALSE or MISLEADING.
     A system that libels the placement cell once is finished, regardless of
     how well it scores on everything else.
  2. HARD CONSTRAINT: zero TRUE confirmations from Tier 0 alone. "No fraud
     rule fired" is not evidence of authenticity; only an agent that found the
     notice on a real source may confirm one. The support caps are supposed to
     enforce this — this is where we check they actually do.
  3. FLOOR, not objective: catch at least MIN_CATCH_RATE of scams. Above the
     floor, catching one more fixture is worth less than the margin it costs.
  4. Tie-break on WORST-CASE MARGIN: of the settings that catch the same
     number of scams, prefer the one where the nearest genuine notice sits
     furthest from the accusation line. Getting every fixture right with a
     genuine notice 0.01 below the line is luck, not safety.

    venv\\Scripts\\python.exe tools\\calibrate_aggregation.py [--write]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_thresholds  # noqa: E402
from app.contracts import Evidence, ForwardMarkers, Strain  # noqa: E402
from app.investigate.aggregate import Aggregator  # noqa: E402
from app.investigate.agents import FraudHeuristics, TemplateProvenance  # noqa: E402
from app.perceive.extract import deterministic_extract  # noqa: E402
from app.perceive.redact import redact_text  # noqa: E402

SCALES = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0]

# Tier 0 is not the last line of defence. It is the free, offline first pass;
# Tier 1 and Tier 2 exist precisely to settle what it cannot. Demanding that
# it catch everything buys the last few percent by running genuine notices
# right up against the accusation line, which is the one trade this system
# must never make.
MIN_CATCH_RATE = 0.70
SATURATIONS = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.4]


def load_rows() -> list[dict]:
    path = ROOT / "fixtures" / "labels.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def prepare(rows: list[dict]) -> list[tuple[dict, object, ForwardMarkers, set[str]]]:
    """Extraction is deterministic and expensive relative to the sweep, so do
    it once instead of once per candidate setting."""
    out = []
    for row in rows:
        red, _ = redact_text(row["text"])
        claim = deterministic_extract(red, report_id=row["id"],
                                      institution_id="fixture-inst",
                                      claim_id="claim-" + row["id"])
        markers = ForwardMarkers(is_forwarded=row.get("forwarded"),
                                 is_frequently_forwarded=row.get("frequently_forwarded"))
        official = {row["institution_domain"]} if row.get("institution_domain") else set()
        out.append((row, claim, markers, official))
    return out


async def score(prepared, scale: float, saturation: float, cfg: dict, bands: dict,
                confirming: list[str]) -> dict:
    aggregator = Aggregator(
        prior_false=cfg["prior_false"], correlated_discount=cfg["correlated_discount"],
        max_abs_log_odds=cfg["max_abs_log_odds"], caps=cfg["caps"],
        reliability=cfg["reliability"], bands=bands,
        log_odds_per_unit_strength=scale,
        confirming_agents=confirming, true_requires_confirmation=True)

    now = datetime.now(timezone.utc)
    libel = caught = confirmed = abstained = exact = 0
    n_true = n_bad = 0
    # Worst-case distance from an error, in posterior units. A setting that
    # gets everything right with a genuine notice sitting 0.01 below the
    # accusation line is not safe, it is lucky.
    margin_true = 1.0
    margin_scam = 1.0
    accuse_line = bands["misleading_above"]

    for row, claim, markers, official in prepared:
        agents = [
            FraudHeuristics(official_domains=official,
                            correlated_discount=cfg["correlated_discount"],
                            saturation=saturation),
            TemplateProvenance(markers),
        ]
        strain = Strain(id="s", first_seen=now, last_seen=now, report_count=1,
                        entities=claim.entities)
        evidence: list[Evidence] = []
        for a in agents:
            if a.applies_to(claim):
                evidence.append(await a.run(claim, strain))
        result = aggregator.aggregate(evidence)
        got = result.label.value
        p_false = result.posterior_false
        want = row["truth"]

        if want == got:
            exact += 1
        if got == "UNVERIFIED":
            abstained += 1
        if want == "TRUE":
            n_true += 1
            margin_true = min(margin_true, accuse_line - p_false)
            if got in ("FALSE", "MISLEADING"):
                libel += 1
            elif got == "TRUE":
                confirmed += 1
        if want in ("FALSE", "MISLEADING"):
            n_bad += 1
            if got in ("FALSE", "MISLEADING"):
                caught += 1
                margin_scam = min(margin_scam, p_false - accuse_line)

    return {"scale": scale, "saturation": saturation, "libel": libel,
            "caught": caught, "n_bad": n_bad, "confirmed": confirmed,
            "n_true": n_true, "abstained": abstained, "exact": exact,
            "margin": round(min(margin_true, margin_scam), 4)}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="write the winner back into config/thresholds.yaml")
    args = ap.parse_args()

    th = get_thresholds()
    cfg = th.get("aggregation")
    bands = th.get("verdict.bands")
    confirming = th.get("verdict.confirming_agents")
    prepared = prepare(load_rows())

    results = []
    for scale in SCALES:
        for sat in SATURATIONS:
            results.append(await score(prepared, scale, sat, cfg, bands, confirming))

    viable = [r for r in results if r["libel"] == 0]
    print(f"{len(viable)}/{len(results)} settings never libel a genuine notice")
    overconfident = [r for r in viable if r["confirmed"] > 0]
    if overconfident:
        print(f"WARNING: {len(overconfident)}/{len(viable)} of those still confirm "
              f"claims TRUE using Tier-0 evidence alone. The support caps in "
              f"thresholds.yaml are meant to make that impossible.")
    viable = [r for r in viable if r["confirmed"] == 0]

    # A single agent at full strength must not be able to exhaust the system's
    # entire confidence budget. If one agent can reach the ±max_abs_log_odds
    # clamp on its own, every other agent's evidence is arithmetically ignored
    # and the cascade, the correlation groups and the caps are all decoration.
    # Requiring at least two full-strength agents to reach the clamp is the
    # weakest form of "this is a multi-agent system" that is still true.
    budget = cfg["max_abs_log_odds"] / 2.0
    over = [r for r in viable if r["scale"] > budget]
    if over:
        print(f"{len(over)} settings let ONE agent exhaust the ±{cfg['max_abs_log_odds']} "
              f"clamp alone; excluded (scale must be <= {budget})")
    viable = [r for r in viable if r["scale"] <= budget]
    print(f"{len(viable)} settings are safe, humble, and genuinely multi-agent")
    if not viable:
        print("NO SAFE SETTING EXISTS. The rule set, not the constants, is wrong.")
        return 1

    competent = [r for r in viable if r["caught"] / max(r["n_bad"], 1) >= MIN_CATCH_RATE]
    print(f"{len(competent)} of those also catch >= {MIN_CATCH_RATE:.0%} of scams at tier 0")
    if competent:
        viable = competent
    else:
        print("WARNING: nothing meets the catch floor; ranking by detection instead")
        viable.sort(key=lambda r: -r["caught"])

    # Among settings that clear the floor, the deciding question is not "which
    # catches one more fixture" but "which leaves the most room before it hurts
    # someone". 35 fixtures cannot tell those apart on accuracy; margin can.
    viable.sort(key=lambda r: (-r["margin"], -r["caught"], r["scale"]))

    # 35 fixtures cannot resolve a 0.02 difference in margin, so treating the
    # top of that list as a winner would be false precision. Take everything
    # within 10% of the best margin as tied, and decide the tie on label
    # sharpness: among equally safe settings, prefer the one that says FALSE
    # rather than MISLEADING, because a hedge the evidence does not require is
    # its own kind of inaccuracy.
    best_margin = viable[0]["margin"]
    tied = [r for r in viable if r["margin"] >= best_margin * 0.90]
    print(f"{len(tied)} settings are within 10% of the best margin ({best_margin:.3f}); "
          f"deciding on label sharpness")
    tied.sort(key=lambda r: (-r["exact"], -r["caught"], -r["margin"]))
    viable = tied + [r for r in viable if r not in tied]

    print()
    print(f"{'scale':>6} {'sat':>5} {'caught':>10} {'confirmed':>11} "
          f"{'abstain':>8} {'exact':>6} {'margin':>8}")
    for r in viable[:12]:
        print(f"{r['scale']:>6.1f} {r['saturation']:>5.1f} "
              f"{r['caught']:>4}/{r['n_bad']:<5} {r['confirmed']:>5}/{r['n_true']:<5} "
              f"{r['abstained']:>8} {r['exact']:>6} {r['margin']:>8.3f}")

    best = viable[0]
    print(f"\nchosen: log_odds_per_unit_strength={best['scale']}  "
          f"agent_saturation={best['saturation']}")
    print(f"  catches {best['caught']}/{best['n_bad']} scams, "
          f"confirms {best['confirmed']}/{best['n_true']} genuine, "
          f"abstains {best['abstained']}/{len(prepared)}, libels 0")
    print(f"  worst-case margin to an error: {best['margin']:.3f} posterior units")

    # The abstention rate is a designed property, not a leftover (ADR-0014).
    lo = th.f("verdict.abstention_target.lo")
    hi = th.f("verdict.abstention_target.hi")
    rate = best["abstained"] / len(prepared)
    if not (lo <= rate <= hi):
        print(f"  NOTE: tier-0 abstention {rate:.0%} sits outside the "
              f"{lo:.0%}-{hi:.0%} target. That target is for the FULL cascade; "
              f"tier 0 alone is expected to abstain more.")

    if args.write:
        path = ROOT / "config" / "thresholds.yaml"
        text = path.read_text(encoding="utf-8")
        text = _replace_scalar(text, "log_odds_per_unit_strength", best["scale"])
        text = _replace_scalar(text, "agent_saturation", best["saturation"])
        path.write_text(text, encoding="utf-8")
        print(f"\nwrote {path}")
    return 0


def _replace_scalar(text: str, key: str, value: float) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            indent = line[: len(line) - len(line.lstrip())]
            comment = line.split("#", 1)[1] if "#" in line else ""
            suffix = f"  #{comment}" if comment else ""
            out.append(f"{indent}{key}: {value}{suffix}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
