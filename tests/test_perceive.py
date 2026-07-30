"""Perceive-layer tests.

The two properties that matter here are not "does it parse" but:
  1. Redaction removes the identifier while KEEPING the part that is evidence
     (ADR-0023). A rule like `personal_upi_vpa` fires on the provider suffix;
     redacting that away silently disarms the detector.
  2. Entity extraction is precise enough to be a HARD GATE (ADR-0008). Recall
     failures cost us a merge; precision failures split one strain into many
     and destroy the whole recognition thesis, so precision is tested harder.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.contracts import ClaimType
from app.perceive.extract import deterministic_extract
from app.perceive.redact import redact_text, reporter_hash

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "labels.jsonl"


def _rows() -> list[dict]:
    return [json.loads(line) for line in FIXTURES.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

def test_redaction_removes_the_phone_number_but_keeps_the_shape() -> None:
    text = "Call 9876543210 to confirm your slot"
    out, found = redact_text(text)
    assert "9876543210" not in out
    assert "phone" in found


def test_redaction_keeps_the_upi_provider_because_it_is_evidence() -> None:
    # `personal_upi_vpa` (strength 0.80) is the single strongest fraud signal
    # we have. It keys off the provider suffix. If redaction ate the suffix the
    # rule would silently never fire and nothing would fail loudly.
    out, found = redact_text("Pay to zentara.hr@okaxis before 5 PM")
    assert "zentara.hr" not in out
    assert out.endswith("before 5 PM")
    assert "@okaxis" in out
    assert "upi" in found


def test_redaction_keeps_the_email_domain_because_it_is_evidence() -> None:
    # `freemail_corporate_recruiting` (0.55) needs the domain.
    out, _ = redact_text("Mail your resume to careers.zentara@gmail.com today")
    assert "careers.zentara" not in out
    assert "@gmail.com" in out


def test_redaction_is_idempotent() -> None:
    once, _ = redact_text("Call 9876543210 or pay a@okaxis")
    twice, _ = redact_text(once)
    assert once == twice


def test_redaction_leaves_ordinary_text_untouched() -> None:
    text = "Placement drive tomorrow in the seminar hall"
    out, found = redact_text(text)
    assert out == text
    assert found == []


def test_pseudonym_is_stable_within_an_epoch_and_never_the_raw_id() -> None:
    salt = "test-salt"
    day0 = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)
    a = reporter_hash("+919876543210", salt, now=day0)
    b = reporter_hash("+919876543210", salt, now=day0 + timedelta(hours=6))
    c = reporter_hash("+919876543210", salt, now=day0 + timedelta(days=40))
    assert a == b, "same reporter inside one salt period must collapse to one identity"
    assert a != c, "the salt must rotate, or the pseudonym is a permanent identifier"
    assert "9876543210" not in a


def test_pseudonym_depends_on_the_salt_so_a_leaked_db_is_not_reversible() -> None:
    now = datetime(2026, 7, 31, tzinfo=timezone.utc)
    assert reporter_hash("+919876543210", "salt-a", now=now) != reporter_hash(
        "+919876543210", "salt-b", now=now
    )


def test_different_reporters_do_not_collide() -> None:
    now = datetime(2026, 7, 31, tzinfo=timezone.utc)
    assert reporter_hash("+919876543210", "s", now=now) != reporter_hash("+919876543211", "s", now=now)


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def test_extraction_finds_the_money_the_rail_and_the_link() -> None:
    text, _ = redact_text(
        "Zentara Systems OFF CAMPUS DRIVE. Registration fee Rs.750 to zentara.hr@okaxis. "
        "Apply at bit.ly/zentara-drive26. Last date tomorrow 5 PM."
    )
    claim = deterministic_extract(text, report_id="r1", institution_id="i1", claim_id="c1")

    assert claim.claim_type is ClaimType.PLACEMENT
    assert 750.0 in claim.entities.amounts
    assert any(u.endswith("@okaxis") for u in claim.entities.upi_handles)
    assert "bit.ly" in claim.entities.domains
    assert "Zentara Systems" in claim.entities.organisations


def test_organisation_extraction_does_not_bleed_into_adjacent_caps() -> None:
    # Regression: "Zentara Systems OFF CAMPUS DRIVE" once produced four
    # organisations including "OFF" and "CAMPUS DRIVE". Every spurious
    # organisation is a hard gate that will refuse a correct strain merge.
    claim = deterministic_extract(
        "Zentara Systems OFF CAMPUS DRIVE registration MANDATORY TOMORROW",
        report_id="r", institution_id="i", claim_id="c",
    )
    assert claim.entities.organisations == ["Zentara Systems"]


def test_out_of_scope_is_detected_so_the_cascade_never_runs() -> None:
    claim = deterministic_extract(
        "The new policy will change everything for our state. Forward to 10 groups.",
        report_id="r", institution_id="i", claim_id="c",
    )
    assert claim.claim_type is ClaimType.OUT_OF_SCOPE


def test_empty_text_degrades_instead_of_raising() -> None:
    claim = deterministic_extract("", report_id="r", institution_id="i", claim_id="c")
    assert claim.extraction_confidence < 0.3
    assert claim.text == ""
    assert claim.degraded is True


def test_code_mixed_text_is_labelled_and_not_dropped() -> None:
    claim = deterministic_extract(
        "Placement drive kal hai, sabhi log 750 rupees fee bharo",
        report_id="r", institution_id="i", claim_id="c",
    )
    # ADR-0006: code-mixing must be *detected*, because it changes which
    # embedding path and which translation step we take. The exact tag matters
    # less than the fact that it is not silently filed as monolingual English.
    assert "mixed" in claim.language
    assert 750.0 in claim.entities.amounts


# --------------------------------------------------------------------------
# Corpus-level properties
# --------------------------------------------------------------------------

def test_claim_type_routing_is_right_on_the_corpus() -> None:
    rows = _rows()
    hits = 0
    for row in rows:
        text, _ = redact_text(row["text"])
        claim = deterministic_extract(text, report_id="r", institution_id="i", claim_id="c")
        hits += claim.claim_type.value == row["claim_type"]
    # Routing only picks which agents run; a miss costs latency, never a wrong
    # verdict. 0.85 is the floor at which routing is still worth doing.
    assert hits / len(rows) >= 0.85, f"claim_type routing regressed to {hits}/{len(rows)}"


def test_every_fixture_survives_the_full_perceive_path() -> None:
    for row in _rows():
        text, _ = redact_text(row["text"])
        claim = deterministic_extract(text, report_id=row["id"], institution_id="i", claim_id="c")
        assert claim.id == "c"
        assert claim.report_id == row["id"]
        assert 0.0 <= claim.extraction_confidence <= 1.0


def test_no_raw_contact_identifier_survives_the_corpus() -> None:
    # A privacy claim is only worth making if it is enforced over real data.
    import re
    leaked: list[str] = []
    for row in _rows():
        text, _ = redact_text(row["text"])
        for m in re.finditer(r"\b[6-9]\d{9}\b", text):
            leaked.append(f"{row['id']}: {m.group(0)}")
        for m in re.finditer(r"\b[\w.\-]{3,}@(?:ok\w+|ybl|paytm|upi)\b", text):
            if not m.group(0).startswith("UPIMASK"):
                leaked.append(f"{row['id']}: {m.group(0)}")
    assert leaked == [], f"raw identifiers survived redaction: {leaked}"


@pytest.mark.parametrize("group", ["placement_fee_scam", "fee_deadline_scam"])
def test_members_of_a_strain_group_share_a_hard_gate_entity(group: str) -> None:
    # This is the empirical precondition for ADR-0008. If members of a known
    # strain share no extractable entity, the hard gate can only ever veto
    # correct merges, and strain memory stops working.
    members = [r for r in _rows() if r["strain_group"] == group]
    assert len(members) >= 2
    sets = []
    for row in members:
        text, _ = redact_text(row["text"])
        e = deterministic_extract(text, report_id="r", institution_id="i", claim_id="c").entities
        sets.append(set(e.organisations) | set(e.upi_handles) | set(e.domains))
    assert set.intersection(*sets), f"{group} members share no gateable entity"
