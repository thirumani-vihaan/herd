# Non-Goals

What a system refuses to do defines it more precisely than what it attempts.
Every item here is a deliberate decision, not a missing feature.

## HERD is not a general fact-checker

It adjudicates **locally verifiable, time-bound, actionable claims** — the kinds
of message that circulate in a college and cause someone to pay money, miss a
deadline, or show up to a place that doesn't exist.

It refuses ([ADR-0024](adr/0024-scope-guard.md)):

| Refused | Why |
|---|---|
| Political and electoral claims | No stable ground truth; verdicts become partisan artifacts; the tool would immediately be used as a weapon |
| Religious or communal claims | Same, with worse consequences |
| Medical advice | Requires clinical authority HERD does not have. Directs to authoritative sources instead. |
| Claims about named private individuals | The defamation surface is unacceptable and the public interest is absent |
| Opinions, predictions, satire | Not falsifiable |

Refusals are explicit and explained in the UI. "Out of scope" is a first-class
outcome, not an error.

The narrowness is the point. A tool trusted for institutional claims can be built
and verified; a tool that adjudicates everything is trusted for nothing.

## HERD does not monitor groups

No group joining, no chat reading, no message scraping, no social graph. Only
what a human explicitly submits.

This costs real capability — the spread model would be far better with true
network data, and targeting could be individual rather than cohort-level. That
cost is accepted permanently. A misinformation tool that surveils to function
would have to be trusted with exactly the data it exists to protect people from
misusing, and no privacy policy substitutes for not collecting it
([ADR-0001](adr/0001-report-driven-not-monitoring.md)).

## HERD does not delete, block, or take down anything

It adds information; it never removes it. No platform integration for removal, no
automated reporting to platforms, no shadowbanning.

The intervention is inoculation of the audience, not suppression of the message.
This keeps HERD outside the censorship debate entirely, and means a wrong verdict
is recoverable — nobody lost their post, they saw a warning that turned out to be
over-cautious.

## HERD does not identify attackers

No attribution, no de-anonymisation, no doxxing of the poster. Evidence describes
**artifacts** — domain age, payment method, template reuse — never people.

Attribution is law enforcement's job and requires powers and accountability a
student project does not have. HERD's output is designed to be *useful to* a
cyber-cell investigation without attempting one.

## HERD does not require an app

Web plus QR is the primary path. Requiring an install before a scam arrives has
the same fatal flaw as backup software that must be running before the deletion:
the people most at risk are exactly the ones who never installed it.

## HERD does not claim to measure true spread

It measures **reported** spread and says so on every chart
([Spread model](04-spread-model.md)). Claims about how many people were reached
are intervals with stated assumptions, never point estimates.

## HERD is not autonomous in the sense of unaccountable

The investigation runs without human input; the *system* does not run without
human oversight. Verdicts are overridable, overrides are public, and appeals have
a published route ([Trust & safety](06-trust-and-safety.md)).

Autonomy here means "no human in the loop of a routine investigation", not "no
human responsible for the outcome."

## Explicitly deferred, not refused

Reasonable and intended, but out of scope for v1:

- Runtime multi-tenancy — per-request tenant resolution, per-tenant auth and
  quotas. The *schema* is multi-tenant from day one and strain memory is already
  global ([ADR-0026](adr/0026-institution-profiles.md)); what is deferred is
  serving several institutions from one process, not the ability to.
- Federated deployments gossiping strain records to each other, which needs a
  trust model between peers that is not worth designing before there is a second
  deployment.
- WhatsApp Business Cloud API ingestion (blocked on Meta business verification)
- On-device inference for fully offline recognition
- Voice-note claims (audio → transcript → existing pipeline)
- A public API for other institutions to query the strain database
