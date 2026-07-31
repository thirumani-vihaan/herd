"""Tier 1: free-tier network checks, ~1-3 s.

Three agents that look at the infrastructure behind a claim rather than its
wording. Tier 0 asks "does this read like a scam"; Tier 1 asks "who actually
owns the thing it is asking you to trust".

Every one of them is split into an offline half and a network half, and the
split is load-bearing rather than defensive. A domain that appends `-placements`
to an institution's own name is identifiable as an impersonation with no network
at all — it is the *string* that gives it away. The network half only adds the
registration date. So when the wifi dies mid-demo these agents get quieter, not
silent, and the answer still arrives.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings, get_thresholds
from app.contracts import Claim, Evidence, Institution, Source, Strain
from app.interfaces import HttpFetcher, InvestigationAgent
from app.investigate.agents._common import (FREEMAIL_DOMAINS, SUSPICIOUS_TLDS,
                                            Finding, Netted, edit_distance,
                                            is_within, label_of, ms_since, net,
                                            registrable, tld_of)

RDAP_BASE = "https://rdap.org/domain/"
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
SAFE_BROWSING_THREATS = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                         "POTENTIALLY_HARMFUL_APPLICATION"]

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
INDIAN_MOBILE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?)?([6-9]\d{9})(?!\d)")
LANDLINE = re.compile(r"(?<!\d)0\d{2,4}[\s\-]?\d{6,8}(?!\d)")
UPI = re.compile(r"\b[\w.\-]{2,}@(?:ok\w+|paytm|ybl|upi|apl|axl|ibl|sbi|hdfcbank|icici|axisbank)\b",
                 re.I)


class _Tier1Agent(InvestigationAgent):
    """Shared plumbing: config resolution, netting, and never raising."""

    name = "Tier1"
    tier = 1
    correlation_group = "independent"
    config_key = ""

    def __init__(self, institution: Institution, fetcher: HttpFetcher | None = None
                 ) -> None:
        self.institution = institution
        self.fetcher = fetcher
        th = get_thresholds()
        self.th = th
        self.discount = th.f("aggregation.correlated_discount")
        self.saturation = th.f("aggregation.agent_saturation")
        self.timeout_s = th.f(f"agents.{self.config_key}.timeout_s")
        self.official_domains = {d.lower().lstrip(".")
                                 for d in (institution.domains.official or [])}

    def s(self, key: str) -> float:
        return self.th.f(f"agents.{self.config_key}.strength.{key}")

    async def run(self, claim: Claim, strain: Strain) -> Evidence:
        started = time.perf_counter()
        try:
            findings, notes, degraded = await self._investigate(claim)
        except Exception as exc:
            return self._unavailable(claim, started, str(exc)[:200],
                                     "agent failed")
        return self._emit(claim, started, findings, notes, degraded)

    async def _investigate(self, claim: Claim
                           ) -> tuple[list[Finding], list[str], bool]:
        raise NotImplementedError

    # -- emitting ----------------------------------------------------------

    def _emit(self, claim: Claim, started: float, findings: list[Finding],
              notes: list[str], degraded: bool) -> Evidence:
        result: Netted = net(findings, discount=self.discount,
                             saturation=self.saturation)
        if result.is_neutral:
            # Nothing found AND the network half failed is a different state
            # from nothing found with everything working. Collapsing them would
            # let a silent outage look like a clean bill of health.
            if degraded and not findings:
                return self._unavailable(claim, started, "; ".join(notes),
                                         "checks could not be completed")
            finding = "; ".join(notes) if notes else self._nothing_found()
            return Evidence(
                agent=self.name, institution_id=claim.institution_id, tier=self.tier,
                status="ok", signal="neutral", strength=0.0, finding=finding,
                sources=[], correlation_group="independent",
                elapsed_ms=ms_since(started))

        headline = "; ".join(f.title for f in result.winners[:3])
        if degraded:
            headline += " (some checks unavailable)"
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="ok", signal=result.signal, strength=result.strength,
            finding=headline,
            sources=[Source(url=f.url or f"herd://{self.name.lower()}/{f.id}",
                            title=f.title, excerpt=f.detail,
                            retrieved_at=datetime.now(timezone.utc), kind=f.kind)
                     for f in result.all_findings],
            correlation_group=result.correlation_group,
            elapsed_ms=ms_since(started))

    def _unavailable(self, claim: Claim, started: float, error: str,
                     finding: str) -> Evidence:
        return Evidence(
            agent=self.name, institution_id=claim.institution_id, tier=self.tier,
            status="unavailable", signal="neutral", strength=0.0, finding=finding,
            sources=[], correlation_group="independent",
            elapsed_ms=ms_since(started), error=error or "unavailable")

    def _nothing_found(self) -> str:
        return "nothing anomalous found"

    # -- shared domain reasoning ------------------------------------------

    def _institution_tokens(self) -> set[str]:
        """Name fragments an impersonator would reuse, from the profile only."""
        min_chars = self.th.i("agents.domain_forensics.impersonation_min_token_chars")
        tokens = {self.institution.id.replace("-", ""),
                  self.institution.short_name.lower().replace(" ", "")}
        for official in self.official_domains:
            tokens.add(label_of(official))
        return {t for t in tokens if t and len(t) >= min_chars}

    def _impersonation(self, domain: str) -> str | None:
        """Why this domain is pretending to be the institution, if it is."""
        if is_within(domain, self.official_domains):
            return None
        label = label_of(domain)
        if not label:
            return None

        for token in self._institution_tokens():
            if token in label and token != label:
                # `somecollege-placements.com`: the college's name is in there,
                # but the college does not own it. A legitimate vendor running
                # a campus portal will trip this too, which is the correct
                # outcome — it is contradicting evidence, not a verdict, and
                # the profile can list the vendor as an official domain.
                return f"uses the institution's name but is not one of its domains"

        max_distance = self.th.i("agents.domain_forensics.lookalike_max_edit_distance")
        min_label = self.th.i("agents.domain_forensics.lookalike_min_label_chars")
        for official in self.official_domains:
            olabel = label_of(official)
            if len(olabel) < min_label:
                continue
            distance = edit_distance(label, olabel, cap=max_distance)
            if 0 < distance <= max_distance:
                return (f"one character-level step away from {official} "
                        f"(distance {distance})")
        return None


class DomainForensics(_Tier1Agent):
    """Who owns the domain, and how long have they owned it.

    A placement portal registered eleven days ago is not a placement portal.
    That single fact settles more campus scams than any amount of text
    analysis, because a scammer can rewrite their wording for free and cannot
    rewrite their WHOIS history at all.
    """

    name = "DomainForensics"
    config_key = "domain_forensics"
    correlation_group = "identity_mismatch"

    def applies_to(self, claim: Claim) -> bool:
        return bool(self._domains(claim)) and claim.in_scope

    def _domains(self, claim: Claim) -> list[str]:
        found = {registrable(d) for d in claim.entities.domains if d}
        found |= {registrable(_host(u)) for u in claim.entities.urls if u}
        return sorted(d for d in found if d and "." in d)

    async def _investigate(self, claim: Claim
                           ) -> tuple[list[Finding], list[str], bool]:
        findings: list[Finding] = []
        notes: list[str] = []
        degraded = False
        domains = self._domains(claim)

        impersonating = False
        for domain in domains:
            reason = self._impersonation(domain)
            if reason is not None:
                impersonating = True
                key = ("lookalike" if "step away" in reason
                       else "impersonating_official")
                findings.append(Finding(
                    id=f"{key}:{domain}", signal="contradicts", strength=self.s(key),
                    title=f"{domain} {reason}",
                    detail=("Compared against the institution's own domains from "
                            "its profile."),
                    url=f"https://{domain}", kind="registry",
                    correlation_group="identity_mismatch"))
            elif tld_of(domain) in SUSPICIOUS_TLDS:
                findings.append(Finding(
                    id=f"suspicious_tld:{domain}", signal="contradicts",
                    strength=self.s("suspicious_tld"),
                    title=f"{domain} uses a bulk-registration TLD",
                    detail=("Cheap TLDs are over-represented in campus scams, but "
                            "plenty of legitimate sites use them — this counts for "
                            "very little on its own."),
                    url=f"https://{domain}", kind="registry",
                    correlation_group="link_obfuscation"))

        official_seen = [d for d in domains if is_within(d, self.official_domains)]
        if official_seen and not impersonating:
            # Only when nothing else in the message is impersonating. A phish
            # that links to the real college site *and* to its own lookalike is
            # using the genuine domain as camouflage, and crediting it there
            # would let the attacker earn trust with the victim's own evidence.
            findings.append(Finding(
                id="official_domain", signal="supports",
                strength=self.s("official_domain"),
                title=f"links to the institution's own domain ({official_seen[0]})",
                detail=("Consistent with a genuine notice, though a message can "
                        "quote a real domain without coming from it."),
                url=f"https://{official_seen[0]}", kind="institutional",
                correlation_group="official_shape"))

        age_findings, age_notes, age_degraded = await self._check_ages(domains)
        findings.extend(age_findings)
        notes.extend(age_notes)
        degraded = degraded or age_degraded
        return findings, notes, degraded

    async def _check_ages(self, domains: list[str]
                          ) -> tuple[list[Finding], list[str], bool]:
        if self.fetcher is None:
            return [], ["domain age not checked (no network client)"], True

        findings: list[Finding] = []
        notes: list[str] = []
        degraded = False
        very_new = self.th.i("agents.domain_forensics.very_new_domain_days")
        new = self.th.i("agents.domain_forensics.new_domain_days")

        for domain in domains:
            if is_within(domain, self.official_domains):
                continue
            try:
                data = await self.fetcher.get_json(RDAP_BASE + domain,
                                                   timeout=self.timeout_s)
            except Exception as exc:
                degraded = True
                notes.append(f"registration date for {domain} unavailable "
                             f"({type(exc).__name__})")
                continue

            registered = _registration_date(data)
            if registered is None:
                notes.append(f"{domain} has no published registration date")
                continue

            age_days = (datetime.now(timezone.utc) - registered).days
            if age_days <= very_new:
                key, phrase = "very_new_domain", "days"
            elif age_days <= new:
                key, phrase = "new_domain", "days"
            else:
                notes.append(f"{domain} registered {age_days} days ago")
                continue
            findings.append(Finding(
                id=f"{key}:{domain}", signal="contradicts", strength=self.s(key),
                title=f"{domain} was registered {age_days} {phrase} ago",
                detail=("Registration date from the domain's RDAP record. An "
                        "institution's own infrastructure is years old."),
                url=RDAP_BASE + domain, kind="registry",
                correlation_group="domain_age"))
        return findings, notes, degraded

    def _nothing_found(self) -> str:
        return "the domains in this message look ordinary"


class URLSafety(_Tier1Agent):
    """Google Safe Browsing, and an explicit refusal to read silence as safety.

    A blocklist hit is near-proof. A miss means almost nothing: Safe Browsing
    lists a domain days after it is reported, and a campus scam link is usually
    hours old, so "no match" is the answer for genuine notices and live scams
    alike. Returning `supports` on a miss would be ADR-0028's mistake in
    miniature — treating an absence of evidence as evidence — so this agent has
    no supporting path at all.
    """

    name = "URLSafety"
    config_key = "url_safety"
    correlation_group = "link_obfuscation"

    def applies_to(self, claim: Claim) -> bool:
        return bool(self._urls(claim)) and claim.in_scope

    def _urls(self, claim: Claim) -> list[str]:
        urls = [u for u in claim.entities.urls if u]
        urls += [f"http://{d}" for d in claim.entities.domains
                 if d and not any(d in u for u in urls)]
        return sorted(set(urls))[:20]

    async def _investigate(self, claim: Claim
                           ) -> tuple[list[Finding], list[str], bool]:
        urls = self._urls(claim)
        key = get_settings().safe_browsing_key
        if not key:
            return [], ["Safe Browsing not configured"], True
        if self.fetcher is None:
            return [], ["Safe Browsing not reachable (no network client)"], True

        body = {
            "client": {"clientId": "herd", "clientVersion": "0.1"},
            "threatInfo": {
                "threatTypes": SAFE_BROWSING_THREATS,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in urls]},
        }
        try:
            data = await self.fetcher.post_json(
                f"{SAFE_BROWSING_URL}?key={key}", json=body, timeout=self.timeout_s)
        except Exception as exc:
            return [], [f"Safe Browsing unavailable ({type(exc).__name__})"], True

        matches = data.get("matches") or []
        if not matches:
            # Said out loud, because the panel showing "checked: clean" without
            # this caveat would be more misleading than not checking at all.
            return [], [f"{len(urls)} link(s) are not on Google's blocklist, which "
                        f"is weak reassurance: new scam domains are usually not "
                        f"listed yet"], False

        findings = []
        for match in matches[:5]:
            threat = str(match.get("threatType", "THREAT")).replace("_", " ").lower()
            url = str((match.get("threat") or {}).get("url", ""))
            findings.append(Finding(
                id=f"threat:{url}", signal="contradicts",
                strength=self.s("threat_match"),
                title=f"Google flags this link as {threat}",
                detail=f"Safe Browsing v4 match on {url}",
                url=url or SAFE_BROWSING_URL, kind="api",
                correlation_group="link_obfuscation"))
        return findings, [], False


class ContactForensics(_Tier1Agent):
    """The email address, phone number and UPI handle you are asked to use.

    This is where money actually moves, so it is the one agent whose findings
    map directly onto the loss. It is also the one most able to libel a real
    person, which is why the UPI check refuses to run against an unverified
    profile: accusing a handle of being unofficial requires actually knowing
    which handles are official.
    """

    name = "ContactForensics"
    config_key = "contact_forensics"
    correlation_group = "identity_mismatch"

    def applies_to(self, claim: Claim) -> bool:
        emails, phones = self._contacts(claim)
        return bool(emails or phones or claim.entities.upi_handles) and claim.in_scope

    def _contacts(self, claim: Claim) -> tuple[list[str], list[str]]:
        text = f"{claim.text} {' '.join(claim.entities.contacts)}"
        emails = sorted({m.lower() for m in EMAIL.findall(text)})
        phones = sorted({m for m in INDIAN_MOBILE.findall(text)})
        return emails, phones

    def _official_email_domains(self) -> set[str]:
        raw = self.institution.domains.email
        values = raw if isinstance(raw, list) else list(raw.get("values") or [])
        return {str(v).lower().lstrip("@").lstrip(".") for v in values if v}

    async def _investigate(self, claim: Claim
                           ) -> tuple[list[Finding], list[str], bool]:
        findings: list[Finding] = []
        notes: list[str] = []
        emails, phones = self._contacts(claim)
        official_email = self._official_email_domains() or self.official_domains

        impersonating = False
        for domain in sorted({d for d in emails}):
            reason = self._impersonation(domain)
            if reason is not None and not is_within(domain, official_email):
                impersonating = True
                key = ("lookalike_email_domain" if "step away" in reason
                       else "impersonating_email_domain")
                findings.append(Finding(
                    id=f"{key}:{domain}", signal="contradicts", strength=self.s(key),
                    title=f"the contact address is at {domain}, which {reason}",
                    detail="Compared against the institution's own mail domains.",
                    url=f"https://{domain}", kind="registry",
                    correlation_group="identity_mismatch"))
            elif domain in FREEMAIL_DOMAINS:
                findings.append(Finding(
                    id=f"freemail:{domain}", signal="contradicts",
                    strength=self.s("freemail_contact"),
                    title=f"replies go to a personal {domain} address, not an "
                          f"institutional one",
                    detail=("Departments answer from their own mail domain; a "
                            "free mailbox leaves no trace to hold anyone to."),
                    url=f"https://{domain}", kind="rule",
                    correlation_group="identity_mismatch"))

        official_contacts = [d for d in emails if is_within(d, official_email)]
        if official_contacts and not impersonating:
            findings.append(Finding(
                id="official_email", signal="supports",
                strength=self.s("official_email"),
                title=f"the contact address is on the institution's own domain "
                      f"({official_contacts[0]})",
                detail="Consistent with a notice that came from inside.",
                url=f"https://{official_contacts[0]}", kind="institutional",
                correlation_group="official_shape"))

        upi_findings, upi_notes = self._check_upi(claim)
        findings.extend(upi_findings)
        notes.extend(upi_notes)

        if phones and not emails and not LANDLINE.search(claim.text):
            findings.append(Finding(
                id="personal_phone_only", signal="contradicts",
                strength=self.s("personal_phone_only"),
                title="the only way to reach the sender is a personal mobile number",
                detail=("Weak on its own — staff use mobiles — but an official "
                        "notice normally carries an office line or a mail address "
                        "as well."),
                url="herd://contactforensics/personal_phone_only", kind="rule",
                correlation_group="identity_mismatch"))

        return findings, notes, False

    def _check_upi(self, claim: Claim) -> tuple[list[Finding], list[str]]:
        handles = sorted({h.lower() for h in claim.entities.upi_handles}
                         | {m.lower() for m in UPI.findall(claim.text)})
        if not handles:
            return [], []

        payments = self.institution.payments
        if not payments.verified:
            # An unverified profile block records what we assume, not what we
            # know. Accusing a payment handle of being unofficial on the basis
            # of an assumed list is how HERD would end up naming a real person
            # as a fraudster because nobody filled in a YAML file.
            return [], [f"a payment handle ({handles[0]}) is present, but this "
                        f"institution's official payment details are unverified, "
                        f"so it cannot be checked"]

        official = {h.lower() for h in payments.official_upi_handles}
        unknown = [h for h in handles if h not in official]
        if not unknown:
            return [], [f"the payment handle {handles[0]} is the institution's own"]

        return [Finding(
            id=f"unofficial_upi:{unknown[0]}", signal="contradicts",
            strength=self.s("unofficial_upi"),
            title=f"payment is requested to {unknown[0]}, which is not one of the "
                  f"institution's published handles",
            detail=("Checked against the institution's verified payment profile."),
            url="herd://contactforensics/unofficial_upi", kind="institutional",
            correlation_group="payment_demand")], []

    def _nothing_found(self) -> str:
        return "the contact details look ordinary"


def _host(url: str) -> str:
    text = (url or "").strip()
    for prefix in ("https://", "http://", "//"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    return text.split("/")[0].split("?")[0].split("@")[-1].split(":")[0]


def _registration_date(data: dict[str, Any]) -> datetime | None:
    for event in data.get("events") or []:
        if str(event.get("eventAction", "")).lower() in {"registration", "created"}:
            raw = str(event.get("eventDate", ""))
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None
