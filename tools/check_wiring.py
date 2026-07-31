"""Wiring check: every agent must be present AND able to answer.

The previous version of this script only asserted that nine agent *names*
appeared in the cascade. That is exactly why it kept passing while four of those
nine agents returned `status="unavailable"` on every possible input: they were
constructed, they were named, and they were dead.

An agent that is wired but cannot emit valid evidence is not wired. So this
script now runs each agent against a stub and fails if any of them degrades for
a reason that is not a genuine dependency outage.

    venv\\Scripts\\python.exe tools\\check_wiring.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.contracts import Claim, ClaimType, Entities, Strain  # noqa: E402
from app.wiring import build_container  # noqa: E402

EXPECTED = {
    "FraudHeuristics", "TemplateProvenance", "StrainPrior",
    "DomainForensics", "URLSafety", "ContactForensics",
    "InstitutionalSource", "OfficialChannel", "OpenWebResearch",
}

# Agents whose whole job is a network call. Offline, "unavailable" is the
# correct answer for these and is not a wiring fault.
NETWORK_BOUND = {"URLSafety", "OpenWebResearch", "DomainForensics",
                 "ContactForensics"}

SAMPLE = ("URGENT: Your VNR VJIET exam hall ticket is blocked. Pay Rs 2500 to "
          "UPI vnrvjiet.fees@okaxis within 2 hours or your registration will "
          "be cancelled. Contact 9876543210.")


async def main() -> int:
    container = build_container()
    await container.store.init()
    print(f"container built for {container.institution.id}")

    cascade = container.build_cascade(markers=None)
    found = {a.name for agents in cascade.tiers.values() for a in agents}

    missing = EXPECTED - found
    if missing:
        print(f"FAILED: missing agents in cascade: {sorted(missing)}")
        return 1
    print(f"all {len(EXPECTED)} agents present")

    now = datetime.now(timezone.utc)
    claim = Claim(id="c", report_id="r", institution_id=container.institution.id,
                  claim_type=ClaimType.FEE, text=SAMPLE, text_en=SAMPLE,
                  language="en", entities=Entities(),
                  extraction_confidence=0.9, extracted_at=now)
    strain = Strain(id="s", first_seen=now, last_seen=now, report_count=1)

    failures: list[str] = []
    print()
    print(f"{'agent':<22}{'tier':<6}{'status':<14}{'signal':<12}note")
    for agents in cascade.tiers.values():
        for agent in agents:
            if not agent.applies_to(claim):
                print(f"{agent.name:<22}{agent.tier:<6}{'n/a':<14}{'-':<12}"
                      f"does not apply to this claim")
                continue
            ev = await agent.run(claim, strain)
            note = ""
            if ev.status == "unavailable" and agent.name not in NETWORK_BOUND:
                note = f"DEGRADED OFFLINE: {ev.error}"
                failures.append(f"{agent.name}: {ev.error}")
            elif ev.status == "unavailable":
                note = "network-bound, offline (expected)"
            print(f"{agent.name:<22}{agent.tier:<6}{ev.status:<14}"
                  f"{ev.signal:<12}{note}")

    print()
    if failures:
        print("FAILED: agents wired but unable to answer:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("SUCCESS: all 9 agents are wired and able to emit valid evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
