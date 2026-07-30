# Trust & Safety

HERD makes public claims about whether other people's messages are true. That is
a position of real power and real liability, and most of the hard problems in
this project live in this document rather than in the machine learning.

## The asymmetry that governs everything

| Error | Cost |
|---|---|
| Calling a scam `UNVERIFIED` | Someone stays cautious for longer than necessary. Recoverable. |
| Calling a real notice `FALSE` | A student misses an actual placement drive. Someone's reputation is publicly damaged. The system's credibility is destroyed. |

These are not symmetric, so the system is not symmetric. Concretely:

- The `FALSE` band requires posterior > 0.90; the abstention band is the widest
  ([Investigation](03-investigation.md)).
- Early cascade exit toward `FALSE` requires more accumulated strength than exit
  toward `UNVERIFIED`.
- Absence of confirmation is never treated as confirmation of absence — the
  institutional-source agent's contradicting strength is capped for exactly this
  reason.
- Any claim naming a **specific private individual** is refused outright
  ([ADR-0024](adr/0024-scope-guard.md)).

## Wording policy

The difference between a useful public-interest tool and a defamation suit is
largely wording ([ADR-0025](adr/0025-wording-policy.md)).

| Never | Always |
|---|---|
| "This is a scam" | "We could not verify this, and these signals are concerning" |
| "X is a fraudster" | "The domain in this message was registered on 26 July 2026" |
| "Fake" as a bare label | `FALSE` with the evidence that produced it, one tap away |

Every user-visible string is generated from evidence, and the post-generation
check rejects any sentence containing an entity that does not appear in the
evidence set. The system states facts and their sources; the reader draws the
conclusion.

## Abuse

Any system that lets users flag content will be used to suppress content.

### Brigading — coordinated false reporting to manufacture a spread curve
- Reporter identities are salted hashes but are still *distinct*, so N reports
  from one pseudonym count once toward velocity.
- Velocity is computed over **distinct reporters**, not reports.
- A strain whose reports come from an implausibly tight cluster of first-seen
  times and a small reporter set is flagged `suspected_coordination` and is
  ineligible to trigger an alert without review.
- Critically: **brigading cannot change a verdict.** Verdicts come from evidence,
  not from report volume. Volume only affects *timing*. This separation is the
  main structural defence, and it is a direct consequence of the decision to keep
  the spread model and the investigation independent.

### Reputation attacks — reporting a legitimate organisation's genuine notice
- Handled by the asymmetry above: without contradicting evidence the verdict is
  `UNVERIFIED`, and `UNVERIFIED` alerts are worded as "we couldn't confirm this
  yet", which is materially different from an accusation.

### Poisoning the herd memory
- A wrong cached verdict propagates to every future match, so cache entries carry
  the confidence they were created with, and low-confidence verdicts are re-run
  rather than served from cache after a TTL.
- Any human override invalidates the cache entry and every strain descended
  from it.

## Privacy

The strongest privacy property is architectural rather than procedural: HERD
cannot leak what it never collects ([ADR-0001](adr/0001-report-driven-not-monitoring.md)).

| Property | Guarantee |
|---|---|
| Group monitoring | Never. HERD does not join, read, or subscribe to any chat. |
| Phone numbers | Never stored. Telegram IDs are salted-hashed on receipt. |
| Reporter identity | Rotating salted hash; salt rotates on a fixed schedule so long-horizon linkage is not possible ([ADR-0004](adr/0004-pseudonymous-reporters.md)). |
| Screenshot contents | Other participants' names/numbers visible in a screenshot are redacted at ingest, before storage. |
| Raw images | Retained only until claim extraction completes, then reduced to hashes unless the reporter opts in to contribute to the template store. |
| Retention | Reports 90 days; strains and verdicts indefinitely (they are the public good); reporter linkage 30 days. |

The screenshot redaction step deserves emphasis: a WhatsApp screenshot is a
photograph of other people's data, and those people did not consent to anything.
Redacting before persistence, not before display, is the only version of that
promise that survives a database breach.

## Human override

The system is designed to be corrected.

- Any verdict can be overridden by a reviewer; the override is recorded with
  `decided_by=human_override` and is visible in the public record.
- Overrides invalidate downstream caches and descendant strains.
- Overrides are the highest-quality training signal available and feed directly
  into agent reliability weights ([Evaluation](07-evaluation.md)).

Being correctable is not an admission of weakness in a system like this. It is
the property that makes deploying it defensible at all.

## Appeals

Any organisation named in a verdict can request review through a published route.
The verdict record includes what evidence would change it — which means an appeal
is not a negotiation but a concrete, checkable request. That is the practical
purpose of the mandatory `what_would_change_my_mind` field.
