# ADR-0004 — Pseudonymous reporter identity

**Status:** Accepted

## Context

The spread model needs to distinguish "20 reports from 20 people" (real spread)
from "20 reports from 1 person" (noise or manipulation). That requires some
notion of reporter identity. But storing identity in a system handling scam
reports creates real risk for the reporter.

## Options

**A. No identity at all.** Maximum privacy. Velocity becomes uncountable and
brigading becomes free.

**B. Store the phone number / Telegram ID.** Simple, enables direct delivery,
and creates a database of people who report scams — precisely the list an
attacker would want.

**C. Static salted hash.** Distinguishable without being reversible, but stable
forever, so a full behavioural history accrues per pseudonym.

**D. Rotating salted hash.** Salt rotates on a schedule; identity is stable within
a window and unlinkable across windows.

## Decision

**D — rotating salted hash**, with a per-installation secret salt rotated every
30 days.

```
reporter_hash = HMAC-SHA256(key=salt_current, msg=raw_identifier)[:16]
```

## Reasoning

Option A fails a requirement the system genuinely has: without distinct
reporters, ten messages from one account look identical to a real outbreak, and
[Trust & safety](../06-trust-and-safety.md)'s brigading defence collapses.

Option B is the default choice and the wrong one. The raw identifier is never
needed — the system only ever needs to answer "is this the same person as that
one?", which is exactly what a hash answers. Storing more than the question
requires is how breaches become harmful.

The rotation in D is the part worth arguing for. A static hash (C) is
irreversible but still accumulates an indefinite behavioural profile: everything
this pseudonym ever reported, forever. Rotation bounds that profile to a window,
which is all the spread model needs — velocity is computed over hours, not years.
The system gets full utility from a 30-day window and gains nothing from a
permanent one, so a permanent one is not kept.

Delivery does not require storing the identifier either: Telegram delivery uses a
chat ID held in the subscription record, kept separately from report history and
deletable independently.

## Consequences

**Accepted costs:**
- Cross-window analytics ("who are our most reliable reporters over a year") are
  impossible by construction. Accepted.
- A determined attacker with the current salt could confirm whether a *specific
  guessed* identifier reported, so the salt is treated as a secret and rotated.

**Gained:**
- The report database is not a list of people.
- Distinct-reporter velocity works, so brigading detection works.
- Reporter linkage expires automatically rather than by policy.
