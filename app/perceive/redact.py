"""Identity and redaction — both run at ingest, before anything is persisted.

Redacting before *display* does not survive a database breach, which is the
threat that matters (docs/06).
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone

# Patterns for third-party PII that arrives inside a forwarded screenshot. The
# reporter chose to send this; the people named in it did not.
PHONE = re.compile(r"(?:\+?\d{1,3}[\s\-]?)?\d{5}[\s\-]?\d{5}|\b\d{10}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
UPI = re.compile(r"\b[A-Za-z0-9._\-]{2,}@(?:okaxis|oksbi|okhdfcbank|okicici|ybl|paytm|upi|ibl|axl)\b")


def reporter_hash(raw_identifier: str, salt: str, period_days: int = 30,
                  now: datetime | None = None) -> str:
    """Rotating salted HMAC (ADR-0004).

    The raw identifier is never persisted, and the salt period means the hash
    stops being a stable identifier after rotation — so it cannot be used to
    build a long-term profile of a reporter even by us.
    """
    now = now or datetime.now(timezone.utc)
    period = int(now.timestamp() // (period_days * 86400))
    msg = f"{raw_identifier}|{period}".encode()
    return hmac.new(salt.encode(), msg, hashlib.sha256).hexdigest()[:32]


def _tag(value: str, prefix: str) -> str:
    """A stable, non-reversible stand-in that still tells two values apart.

    This distinction is load-bearing and was found by a failing test rather
    than by reading the code. A mask that collapses every UPI handle to one
    literal is privacy-preserving but destroys the ADR-0008 payment-rail hard
    gate: two scams collecting at different accounts would look identical and
    merge into one strain, and the warning would then name the wrong account.

    A short digest keeps the property we actually need — same handle maps to
    the same tag, different handles map to different tags — while the handle
    itself is unrecoverable from the tag.
    """
    digest = hashlib.blake2b(value.lower().encode(), digest_size=3).hexdigest()
    return f"{prefix}{digest}"


def redact_text(text: str) -> tuple[str, list[str]]:
    """Mask third-party contact details, keeping enough shape for the rules.

    A UPI handle is evidence — `personal_upi_vpa` is an 0.80-strength rule — so
    the handle's *provider* survives while the account name does not. Losing the
    signal entirely to protect a scammer's privacy would be the wrong trade.
    """
    found: list[str] = []

    def upi_sub(m: re.Match) -> str:
        found.append("upi")
        local, _, provider = m.group(0).partition("@")
        return f"{_tag(local, 'UPI')}@{provider}"

    def phone_sub(m: re.Match) -> str:
        found.append("phone")
        digits = re.sub(r"\D", "", m.group(0))
        return _tag(digits, "PHONE")

    def email_sub(m: re.Match) -> str:
        found.append("email")
        local, _, domain = m.group(0).partition("@")
        return f"{_tag(local, 'EMAIL')}@{domain}"

    out = UPI.sub(upi_sub, text)
    out = EMAIL.sub(email_sub, out)
    out = PHONE.sub(phone_sub, out)
    return out, found


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
