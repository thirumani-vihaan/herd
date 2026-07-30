"""Tests for Tier 1 — the agents that look at infrastructure, not wording.

The theme running through all of these is that each agent has an offline half
and a network half, and the offline half is the one that catches scams. A test
suite that only exercised these with a working network would be testing the
half that stops working during the demo.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.contracts import (Claim, ClaimType, Entities, Institution, PaymentSpec,
                           Domains, Strain)
from app.investigate.agents._common import (edit_distance, is_within, label_of,
                                            registrable, tld_of)
from app.investigate.agents.tier1 import (ContactForensics, DomainForensics,
                                          URLSafety)
from tests.fakes import OfflineFetcher, ScriptedFetcher

HERE = "vnrvjiet"


def institution(*, upi_verified: bool = False,
                upi: list[str] | None = None) -> Institution:
    return Institution(
        id=HERE, display_name="VNR VJIET", short_name="vnrvjiet",
        domains=Domains(official=["vnrvjiet.ac.in"], email=["vnrvjiet.in"]),
        payments=PaymentSpec(verified=upi_verified,
                             official_upi_handles=upi or []))


def claim(text: str = "x" * 60, **entity_kwargs) -> Claim:
    return Claim(id="c", report_id="r", institution_id=HERE,
                 claim_type=ClaimType.PLACEMENT, text=text, text_en=text,
                 language="en", entities=Entities(**entity_kwargs),
                 extraction_confidence=0.9,
                 extracted_at=datetime.now(timezone.utc))


def strain() -> Strain:
    now = datetime.now(timezone.utc)
    return Strain(id="s", first_seen=now, last_seen=now, report_count=1)


def go(agent, c: Claim):
    return asyncio.run(agent.run(c, strain()))


def rdap(days_ago: int) -> dict:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"events": [{"eventAction": "registration",
                        "eventDate": when.isoformat().replace("+00:00", "Z")}]}


# --------------------------------------------------------------------------
# Domain arithmetic
# --------------------------------------------------------------------------

@pytest.mark.parametrize("host,expected", [
    ("vnrvjiet.ac.in", "vnrvjiet.ac.in"),
    ("placements.vnrvjiet.ac.in", "vnrvjiet.ac.in"),
    ("www.example.com", "example.com"),
    ("a.b.example.co.uk", "example.co.uk"),
    ("example.com", "example.com"),
])
def test_registrable_domain_handles_two_part_suffixes(host, expected):
    # Without the multi-part suffix table, every Indian college reduces to
    # 'ac.in' and the lookalike check accuses all of them of being each other.
    assert registrable(host) == expected


def test_a_colleges_own_subdomain_is_not_an_impostor():
    assert is_within("placements.vnrvjiet.ac.in", {"vnrvjiet.ac.in"})
    assert not is_within("vnrvjiet.ac.in.scam.com", {"vnrvjiet.ac.in"})


def test_suffix_confusion_does_not_make_unrelated_colleges_lookalikes():
    assert label_of("cbit.ac.in") != label_of("vnrvjiet.ac.in")
    assert edit_distance("cbit", "vnrvjiet", cap=2) > 2


def test_edit_distance_gives_up_rather_than_returning_a_number_it_cannot_defend():
    assert edit_distance("a" * 40, "b" * 40, cap=3) == 4


def test_tld_extraction_survives_multi_part_suffixes():
    assert tld_of("vnrvjiet.ac.in") == "in"
    assert tld_of("scam.online") == "online"


# --------------------------------------------------------------------------
# DomainForensics — offline half
# --------------------------------------------------------------------------

def test_a_domain_wearing_the_colleges_name_is_flagged_with_no_network():
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["vnrvjiet-placements.online"]))
    assert ev.status == "ok"
    assert ev.signal == "contradicts"
    assert ev.strength > 0
    assert "vnrvjiet-placements.online" in ev.finding


def test_a_transposed_letter_is_caught_as_a_lookalike():
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["vnrvjeit.ac.in"]))
    assert ev.signal == "contradicts"
    assert "step away" in " ".join(s.title for s in ev.sources)


def test_the_colleges_own_domain_is_never_reported_as_an_impostor():
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["placements.vnrvjiet.ac.in"]))
    assert ev.signal in {"supports", "neutral"}


def test_an_unrelated_company_domain_is_not_accused():
    # A genuine placement notice links to the recruiter. Flagging that would
    # make HERD contradict every real drive it ever sees.
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["careers.tcs.com"]))
    assert ev.signal == "neutral"


def test_a_real_domain_beside_a_fake_one_earns_no_credit():
    # Good phishing quotes the genuine site next to its own. Crediting the
    # genuine one would let the attacker buy trust with the victim's evidence.
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["vnrvjiet.ac.in", "vnrvjiet-verify.xyz"]))
    assert ev.signal == "contradicts"
    assert not any("own domain" in s.title for s in ev.sources)


def test_a_cheap_tld_alone_is_the_weakest_thing_the_agent_can_say():
    agent = DomainForensics(institution(), OfflineFetcher())
    weak = go(agent, claim(domains=["campusdrive2026.xyz"]))
    strong = go(agent, claim(domains=["vnrvjiet-drive.com"]))
    assert weak.signal == "contradicts"
    assert weak.strength < strong.strength


def test_it_does_not_run_at_all_when_there_is_no_domain_to_examine():
    # Rule 4 of the agent contract: applicability is declared, and a claim with
    # no links must not cost a network round trip.
    agent = DomainForensics(institution(), OfflineFetcher())
    assert agent.applies_to(claim()) is False


def test_the_network_half_failing_does_not_silence_the_offline_half():
    fetcher = OfflineFetcher()
    agent = DomainForensics(institution(), fetcher)
    ev = go(agent, claim(domains=["vnrvjiet-placements.online"]))
    assert ev.status == "ok"
    assert ev.strength > 0
    assert "unavailable" in ev.finding


def test_with_nothing_to_say_and_a_dead_network_it_admits_it_is_blind():
    # The dangerous alternative is reporting 'nothing anomalous found' when the
    # truth is 'nothing was checked'.
    agent = DomainForensics(institution(), OfflineFetcher())
    ev = go(agent, claim(domains=["careers.tcs.com"]))
    assert ev.status == "unavailable"
    assert ev.strength == 0.0


# --------------------------------------------------------------------------
# DomainForensics — network half
# --------------------------------------------------------------------------

def test_a_domain_registered_last_week_is_strong_evidence():
    agent = DomainForensics(institution(),
                            ScriptedFetcher({"rdap.org": rdap(6)}))
    ev = go(agent, claim(domains=["campusdrive2026.com"]))
    assert ev.signal == "contradicts"
    assert "registered 6 days ago" in " ".join(s.title for s in ev.sources)


def test_an_old_domain_produces_no_accusation():
    agent = DomainForensics(institution(),
                            ScriptedFetcher({"rdap.org": rdap(4000)}))
    ev = go(agent, claim(domains=["careers.tcs.com"]))
    assert ev.signal == "neutral"
    assert ev.status == "ok"


def test_a_younger_domain_counts_for_more_than_a_merely_new_one():
    fresh = DomainForensics(institution(), ScriptedFetcher({"rdap.org": rdap(5)}))
    newish = DomainForensics(institution(), ScriptedFetcher({"rdap.org": rdap(60)}))
    a = go(fresh, claim(domains=["campusdrive2026.com"]))
    b = go(newish, claim(domains=["campusdrive2026.com"]))
    assert a.strength > b.strength


def test_the_institutions_own_domain_is_not_sent_to_the_registry():
    fetcher = ScriptedFetcher({"rdap.org": rdap(4000)})
    agent = DomainForensics(institution(), fetcher)
    go(agent, claim(domains=["vnrvjiet.ac.in"]))
    assert fetcher.calls == []


def test_a_registry_with_no_registration_date_is_not_invented():
    agent = DomainForensics(institution(), ScriptedFetcher({"rdap.org": {}}))
    ev = go(agent, claim(domains=["careers.tcs.com"]))
    assert ev.signal == "neutral"
    assert "no published registration date" in ev.finding


# --------------------------------------------------------------------------
# URLSafety
# --------------------------------------------------------------------------

def test_a_blocklist_hit_is_close_to_conclusive():
    agent = URLSafety(institution(), ScriptedFetcher({"safebrowsing": {
        "matches": [{"threatType": "SOCIAL_ENGINEERING",
                     "threat": {"url": "http://scam.example/apply"}}]}}))
    ev = go(agent, claim(urls=["http://scam.example/apply"]))
    assert ev.signal == "contradicts"
    assert ev.strength > 0.6


def test_a_clean_result_is_never_treated_as_evidence_of_safety():
    # Safe Browsing lists domains days after they are reported and campus scam
    # links are hours old, so 'no match' is the answer for live scams too.
    # Reading it as reassurance is ADR-0028's mistake in miniature.
    agent = URLSafety(institution(), ScriptedFetcher({"safebrowsing": {}}))
    ev = go(agent, claim(urls=["http://scam.example/apply"]))
    assert ev.signal == "neutral"
    assert ev.strength == 0.0


def test_a_clean_result_says_out_loud_how_weak_it_is():
    agent = URLSafety(institution(), ScriptedFetcher({"safebrowsing": {}}))
    ev = go(agent, claim(urls=["http://scam.example/apply"]))
    assert "weak reassurance" in ev.finding


def test_no_links_means_no_api_call():
    fetcher = ScriptedFetcher({"safebrowsing": {}})
    agent = URLSafety(institution(), fetcher)
    assert agent.applies_to(claim()) is False
    assert fetcher.calls == []


def test_a_dead_api_degrades_rather_than_reassuring():
    agent = URLSafety(institution(), OfflineFetcher())
    ev = go(agent, claim(urls=["http://scam.example/apply"]))
    assert ev.status == "unavailable"
    assert ev.strength == 0.0


# --------------------------------------------------------------------------
# ContactForensics
# --------------------------------------------------------------------------

def test_a_free_mailbox_for_an_official_drive_is_contradicting_evidence():
    agent = ContactForensics(institution(), OfflineFetcher())
    ev = go(agent, claim("Contact tcs.hr.official@gmail.com to register" + " x" * 20,
                         contacts=["tcs.hr.official@gmail.com"]))
    assert ev.signal == "contradicts"


def test_an_address_on_the_colleges_own_mail_domain_supports_the_claim():
    agent = ContactForensics(institution(), OfflineFetcher())
    ev = go(agent, claim("Contact placements@vnrvjiet.in for details" + " x" * 20,
                         contacts=["placements@vnrvjiet.in"]))
    assert ev.signal == "supports"


def test_an_unofficial_payment_handle_is_flagged_when_the_profile_is_verified():
    inst = institution(upi_verified=True, upi=["vnrvjiet@sbi"])
    agent = ContactForensics(inst, OfflineFetcher())
    ev = go(agent, claim("Pay the fee to hr.tcsdrive@okaxis now" + " x" * 20,
                         upi_handles=["hr.tcsdrive@okaxis"]))
    assert ev.signal == "contradicts"
    assert "hr.tcsdrive@okaxis" in ev.finding


def test_an_unverified_payment_profile_produces_a_caveat_not_an_accusation():
    # Naming a real person's payment handle as fraudulent because nobody filled
    # in a YAML file is the single most defamatory thing HERD could do.
    agent = ContactForensics(institution(upi_verified=False), OfflineFetcher())
    ev = go(agent, claim("Pay the fee to hr.tcsdrive@okaxis now" + " x" * 20,
                         upi_handles=["hr.tcsdrive@okaxis"]))
    assert ev.signal != "contradicts"
    assert "unverified" in ev.finding


def test_the_colleges_own_handle_is_not_flagged():
    inst = institution(upi_verified=True, upi=["vnrvjiet@sbi"])
    agent = ContactForensics(inst, OfflineFetcher())
    ev = go(agent, claim("Pay the exam fee to vnrvjiet@sbi" + " x" * 20,
                         upi_handles=["vnrvjiet@sbi"]))
    assert ev.signal != "contradicts"


def test_a_lookalike_mail_domain_outweighs_a_merely_free_one():
    agent = ContactForensics(institution(), OfflineFetcher())
    fake = go(agent, claim("Write to hr@vnrvjiet-placements.com" + " x" * 20,
                           contacts=["hr@vnrvjiet-placements.com"]))
    free = go(agent, claim("Write to hr.tcs@gmail.com" + " x" * 20,
                           contacts=["hr.tcs@gmail.com"]))
    assert fake.strength > free.strength


def test_a_mobile_number_alone_is_the_weakest_signal_the_agent_has():
    # Staff genuinely use mobiles. This must never be the reason a notice is
    # called false.
    agent = ContactForensics(institution(), OfflineFetcher())
    ev = go(agent, claim("Call 9876543210 for details" + " x" * 20,
                         contacts=["9876543210"]))
    assert ev.signal == "contradicts"
    assert ev.strength < 0.3


def test_an_office_landline_beside_a_mobile_is_not_suspicious():
    agent = ContactForensics(institution(), OfflineFetcher())
    ev = go(agent, claim("Call 040 23042758 or 9876543210" + " x" * 20,
                         contacts=["9876543210"]))
    assert ev.signal == "neutral"


def test_no_contact_details_means_the_agent_does_not_run():
    agent = ContactForensics(institution(), OfflineFetcher())
    assert agent.applies_to(claim()) is False


def test_contact_forensics_never_needs_the_network():
    # It is Tier 1 because it depends on the institution profile, not because
    # it makes a request. A demo with no network must lose nothing here.
    fetcher = OfflineFetcher()
    agent = ContactForensics(institution(), fetcher)
    ev = go(agent, claim("Contact tcs.hr@gmail.com" + " x" * 20,
                         contacts=["tcs.hr@gmail.com"]))
    assert fetcher.calls == []
    assert ev.status == "ok"


# --------------------------------------------------------------------------
# Contract compliance, for all three
# --------------------------------------------------------------------------

@pytest.mark.parametrize("factory", [DomainForensics, URLSafety, ContactForensics])
def test_no_tier1_agent_raises_however_broken_its_dependency(factory):
    class Exploding:
        async def get_json(self, *a, **k): raise RuntimeError("boom")
        async def get_text(self, *a, **k): raise RuntimeError("boom")
        async def post_json(self, *a, **k): raise RuntimeError("boom")

    agent = factory(institution(), Exploding())
    ev = go(agent, claim("Pay hr@vnrvjiet-fake.xyz 9876543210" + " x" * 20,
                         domains=["vnrvjiet-fake.xyz"],
                         urls=["http://vnrvjiet-fake.xyz"],
                         contacts=["hr@vnrvjiet-fake.xyz"]))
    assert ev.agent == factory.name
    assert ev.tier == 1


@pytest.mark.parametrize("factory", [DomainForensics, URLSafety, ContactForensics])
def test_every_non_neutral_finding_carries_a_citation(factory):
    agent = factory(institution(upi_verified=True, upi=["vnrvjiet@sbi"]),
                    ScriptedFetcher({"rdap.org": rdap(4),
                                     "safebrowsing": {"matches": [
                                         {"threatType": "SOCIAL_ENGINEERING",
                                          "threat": {"url": "http://x.xyz"}}]}}))
    ev = go(agent, claim("Pay hr.tcsdrive@okaxis at http://vnrvjiet-fake.xyz"
                         + " x" * 20,
                         domains=["vnrvjiet-fake.xyz"],
                         urls=["http://vnrvjiet-fake.xyz"],
                         contacts=["hr@gmail.com"],
                         upi_handles=["hr.tcsdrive@okaxis"]))
    if ev.signal != "neutral":
        assert ev.sources, "a non-neutral finding must cite something"
        assert all(s.url for s in ev.sources)


@pytest.mark.parametrize("factory", [DomainForensics, URLSafety, ContactForensics])
def test_an_unavailable_agent_carries_no_weight(factory):
    agent = factory(institution(), OfflineFetcher())
    ev = go(agent, claim("http://careers.tcs.com" + " x" * 20,
                         domains=["careers.tcs.com"],
                         urls=["http://careers.tcs.com"],
                         contacts=["hr@careers.tcs.com"]))
    if ev.status != "ok":
        assert ev.strength == 0.0
        assert ev.signal == "neutral"


def test_tier1_carries_no_institutional_string_of_its_own():
    # The portability claim: switching HERD_INSTITUTION must change behaviour
    # with no code change. Every institutional fact here arrives via the
    # injected profile.
    other = Institution(id="cbit", display_name="CBIT", short_name="cbit",
                        domains=Domains(official=["cbit.ac.in"], email=["cbit.ac.in"]))
    agent = DomainForensics(other, OfflineFetcher())
    ev = go(agent, claim(domains=["cbit-placements.online"]))
    assert ev.signal == "contradicts"

    # ...and the previous institution's lookalike is now just a stranger.
    ev2 = go(agent, claim(domains=["careers.tcs.com"]))
    assert ev2.signal == "neutral"
