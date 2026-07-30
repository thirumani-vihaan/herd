"""Tier-0 agents: free, deterministic, ~30 ms, and enough on their own.

These two are the reason the demo survives a dead network. Everything above
Tier 0 makes the answer better; Tier 0 makes it exist.

Neither returns a label. Both cite themselves.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import get_thresholds
from app.contracts import Claim, Evidence, ForwardMarkers, Source, Strain
from app.interfaces import InvestigationAgent

RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "fraud_rules.yaml"

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "rb.gy", "cutt.ly",
              "shorturl.at", "is.gd", "ow.ly", "buff.ly", "rebrand.ly", "tiny.cc"}
FREEMAIL = {"gmail.com", "yahoo.com", "yahoo.in", "hotmail.com", "outlook.com",
            "rediffmail.com", "protonmail.com", "icloud.com", "aol.com"}
URGENCY_NOW = re.compile(r"\b(register now|apply now|hurry|last date|immediately|"
                         r"before it'?s too late|closing soon|today only)\b", re.I)
URGENCY_SCARCE = re.compile(r"\b(limited slots?|few seats?|only \d+ seats?|"
                            r"limited seats?|first come)\b", re.I)
SOON = re.compile(r"\b(today|tomorrow|tonight|within \d+ ?(hours?|hrs?)|by \d{1,2} ?(am|pm))\b", re.I)
MESSAGING_ONLY = re.compile(r"\b(whats ?app|telegram|dm me|inbox me|ping me on)\b", re.I)
PAYMENT_ASK = re.compile(r"\b(pay|fee|fees|charge|charges|amount payable|deposit|"
                         r"transfer|registration fee|processing fee|refundable)\b", re.I)
# "No registration fee" is the single most common phrase in a GENUINE notice,
# because genuine notices say it to distinguish themselves from scams. Matching
# it as a payment demand would make the system punish exactly the text written
# to reassure people — the shortest path to libelling the placement cell.
NEGATED_PAYMENT = re.compile(
    r"\b(no|not|non|without|free of|zero|nil|never|nahi|nahin)\b[^.\n]{0,24}?"
    r"\b(fee|fees|charge|charges|payment|paid|cost|money)\b", re.I)
JOB_CONTEXT = re.compile(r"\b(drive|recruit\w*|hiring|placement|internship|job|"
                         r"walk-?in|offer letter)\b", re.I)


def load_rules(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((path or RULES_PATH).read_text(encoding="utf-8"))
    return {r["id"]: r for r in data["rules"]}


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class FraudHeuristics(InvestigationAgent):
    """Structural rules over the claim text. No model, no network.

    Every rule cites itself by id, so the reasoning shown to a student is
    auditable line by line rather than "the AI thought so".

    The rule set includes SUPPORTING rules, and that is deliberate. A rule set
    that can only ever accuse will eventually accuse a genuine notice, because
    nothing in it is capable of pushing the posterior the other way.
    """

    name = "FraudHeuristics"
    tier = 0
    correlation_group = "heuristic"

    def __init__(self, rules: dict[str, dict[str, Any]] | None = None,
                 official_domains: set[str] | None = None,
                 correlated_discount: float | None = None,
                 saturation: float | None = None) -> None:
        self.rules = rules if rules is not None else load_rules()
        # Injected from the institution profile. Never hardcoded: the whole
        # portability claim rests on `app/` containing no institutional string.
        self.official_domains = {d.lower().lstrip(".") for d in (official_domains or set())}
        # Resolved from config rather than defaulted in the signature. A
        # default here would be a second, stale copy of a calibrated value that
        # silently wins whenever a caller forgets to pass it — and it would
        # keep winning after recalibration moved the real one.
        th = get_thresholds()
        self.correlated_discount = (th.f("aggregation.correlated_discount")
                                    if correlated_discount is None else correlated_discount)
        self.saturation = (th.f("aggregation.agent_saturation")
                           if saturation is None else saturation)

    def applies_to(self, claim: Claim) -> bool:
        return claim.claim_type.value != "out_of_scope"

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            fired = self._fire(claim)
        except Exception as exc:  # an agent may never raise
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="rule evaluation failed", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started),
                error=str(exc)[:200])

        if not fired:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="neutral", strength=0.0,
                finding="no structural fraud indicators matched", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started))

        # The strongest single rule sets nothing on its own. Contradicting and
        # supporting rules are both accumulated and NETTED, because a message
        # that asks for money AND links only to the college's own domain is
        # genuinely ambiguous, and a rule engine that reports only the louder
        # half of what it found is not reporting what it found.
        contra, contra_rules = self._accumulate(fired, "contradicts")
        supp, supp_rules = self._accumulate(fired, "supports")
        net = contra - supp

        if abs(net) < 1e-9:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="neutral", strength=0.0,
                finding="fraud indicators and reassuring indicators cancelled out",
                sources=[], correlation_group="independent", elapsed_ms=_ms(started))

        signal = "contradicts" if net > 0 else "supports"
        chosen = contra_rules if net > 0 else supp_rules
        strength = min(1.0, abs(net) / self.saturation)

        finding = "; ".join(f["title"] for f in chosen[:4])
        # Cite every rule that fired, including the ones on the losing side.
        # Hiding them would make the panel a summary of the verdict instead of
        # a record of the evidence.
        cited = chosen + [f for f in fired if f not in chosen]
        sources = [Source(url=f"herd://rules/{f['id']}", title=f["title"],
                          excerpt=f.get("rationale", ""),
                          retrieved_at=datetime.now(timezone.utc), kind="rule")
                   for f in cited]

        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal=signal, strength=strength,
            finding=finding, sources=sources,
            correlation_group=chosen[0].get("correlation_group", "independent"),
            elapsed_ms=_ms(started))

    def _accumulate(self, fired: list[dict[str, Any]], signal: str
                    ) -> tuple[float, list[dict[str, Any]]]:
        """Sum one direction's rules with the same group discipline the
        aggregator uses: independent groups add, co-occurring rules inside one
        group do not.

        `url_shortener`, `freemail` and `sender_mismatch` are three faces of one
        attack kit. Adding them as if they were three separate discoveries is
        how a rule engine convinces itself.
        """
        side = [f for f in fired if f["signal"] == signal]
        side.sort(key=lambda f: -float(f["strength"]))
        groups: dict[str, list[float]] = {}
        for f in side:
            groups.setdefault(f.get("correlation_group", "independent"), []).append(
                float(f["strength"]))
        total = 0.0
        for weights in groups.values():
            total += weights[0] + self.correlated_discount * sum(weights[1:])
        return total, side

    def _fire(self, claim: Claim) -> list[dict[str, Any]]:
        low = (claim.text or "").lower()
        ent = claim.entities
        ctype = claim.claim_type.value
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()

        def hit(rule_id: str) -> None:
            rule = self.rules.get(rule_id)
            if rule and rule_id not in seen and ctype in rule.get("applies_to", []):
                seen.add(rule_id)
                hits.append(rule)

        domains = {d.lower() for d in ent.domains}
        # Excise negated payment phrases before looking for a payment demand,
        # rather than letting one negation anywhere in the message suppress a
        # real demand elsewhere in it. A scam that says "no hidden charges" and
        # then asks for Rs 750 still asks for Rs 750.
        payable = NEGATED_PAYMENT.sub(" ", low)
        # A bare number is not a payment demand — "Package: 12 LPA" is an
        # amount too. Money is only being asked for if something asks for it.
        asks_money = bool(PAYMENT_ASK.search(payable))
        job_context = ctype == "placement" or bool(JOB_CONTEXT.search(low))

        if asks_money and job_context:
            hit("upfront_fee_for_job")
        if ent.upi_handles:
            hit("personal_upi_vpa")
        if domains & FREEMAIL:
            hit("freemail_corporate_recruiting")
        if domains & SHORTENERS:
            hit("url_shortener_on_official_link")
        if MESSAGING_ONLY.search(low) and not (domains - SHORTENERS - FREEMAIL):
            hit("personal_messaging_contact_only")
        if SOON.search(low) and (asks_money or job_context):
            hit("deadline_under_48h")
        if URGENCY_SCARCE.search(low) and URGENCY_NOW.search(low):
            hit("limited_slots_register_now")
        if ent.organisations and (ent.upi_handles or (domains & FREEMAIL)):
            hit("sender_domain_mismatch")

        # The supporting side. Without it the rule set can only ever accuse.
        if domains and self.official_domains and self._all_official(domains):
            hit("official_domain_link")
        if not asks_money and not ent.upi_handles:
            hit("no_payment_requested")

        return hits

    def _all_official(self, domains: set[str]) -> bool:
        """True only if every linked domain is the institution's own.

        Deliberately strict. One off-domain link in an otherwise clean notice is
        exactly how a real announcement gets weaponised, so "mostly official"
        earns nothing.
        """
        return all(self._match_official(d) is not None for d in domains)

    def _match_official(self, domain: str) -> str | None:
        for off in self.official_domains:
            if domain == off or domain.endswith("." + off):
                return off
        return None


class TemplateProvenance(InvestigationAgent):
    """Forwarding provenance read off the screenshot's own chrome (ADR-0018).

    WhatsApp's "Forwarded many times" marker is the highest-value spread signal
    in this system and it is free: it is rendered into the image the reporter
    already sent. A message that had been forwarded many times before it
    reached us has a history we never had to measure.

    It is evidence about SPREAD, not about truth, so its strength is modest and
    its direction is at most weakly contradicting. Genuine notices get forwarded
    too; treating "widely forwarded" as "false" would be precisely the reasoning
    error this system exists to correct.

    Markers belong to the Report, so the cascade constructs this agent per
    investigation. That keeps the frozen `run(claim, strain)` signature intact
    instead of smuggling report state through the claim.
    """

    name = "TemplateProvenance"
    tier = 0
    correlation_group = "provenance"

    def __init__(self, markers: ForwardMarkers | None = None) -> None:
        self.markers = markers

    def applies_to(self, claim: Claim) -> bool:
        return True

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            m = self.markers
            freq = bool(m and m.is_frequently_forwarded)
            fwd = bool(m and m.is_forwarded)
            prior = max(0, strain.report_count - 1)

            if freq:
                signal, strength = "contradicts", 0.15
                finding = ("the screenshot carries WhatsApp's 'forwarded many times' "
                           "marker, so it had already travelled before it reached us")
            elif fwd and prior >= 2:
                signal, strength = "contradicts", 0.08
                finding = (f"forwarded message, and this template had already been "
                           f"reported {prior} times before this one")
            elif fwd:
                signal, strength = "neutral", 0.0
                finding = "forwarded message, with no further provenance signal"
            elif m is None:
                signal, strength = "neutral", 0.0
                finding = "no forwarding chrome was readable in the screenshot"
            else:
                signal, strength = "neutral", 0.0
                finding = "no forwarding markers visible in the screenshot"

            sources = ([Source(url="herd://provenance/forward-markers",
                               title="Forwarding markers in the submitted screenshot",
                               excerpt=finding,
                               retrieved_at=datetime.now(timezone.utc), kind="memory")]
                       if strength > 0 else [])

            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal=signal, strength=strength, finding=finding,
                sources=sources, correlation_group=self.correlation_group,
                elapsed_ms=_ms(started))
        except Exception as exc:
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="unavailable", signal="neutral", strength=0.0,
                finding="provenance unavailable", sources=[],
                correlation_group="independent", elapsed_ms=_ms(started),
                error=str(exc)[:200])
