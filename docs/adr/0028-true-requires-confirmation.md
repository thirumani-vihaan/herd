# ADR-0028: TRUE is not reachable by arithmetic alone

**Status:** Accepted
**Date:** During P5 (investigation layer)
**Related:** ADR-0013 (aggregation), ADR-0014 (verdict bands), ADR-0026 (institution scoping)

## Context

Once ADR-0027 made the verdict bands reachable, the first calibration run
produced a result that looked excellent and was not:

```
scale 5.0, saturation 1.8 — catches 13/16 scams, confirms 13/14 genuine, libels 0
```

Tier 0 was confirming thirteen out of fourteen genuine notices as **TRUE**,
using only `FraudHeuristics` and `TemplateProvenance` — two agents that never
touch the network, never contact the institution, and never look at any source.

The evidence supporting each of those confirmations was, in substance, *no
fraud rule fired*. The supporting rules that pushed the posterior down are
`no_payment_requested` and `official_domain_link`, and while both are reasonable
things to notice, neither one establishes that a notice is real.

**Absence of fraud indicators is not evidence of authenticity.** It is equally
consistent with:

- a scam written carefully enough not to trip a published rule set,
- a credential phish that asks for a login rather than money, so
  `no_payment_requested` fires *in its favour*,
- a genuine template with one altered date, where every structural signal is
  authentic because most of the message is,
- any claim about an event that simply has not happened.

The failure mode this creates is worse than the one the system was built to
prevent. A student who is told "HERD says this is FALSE" and ignores it has lost
nothing. A student who is told "HERD says this is TRUE" and acts on it has been
actively misled by the thing that was supposed to protect them — and the whole
value of the product is that its output can be trusted more than the forward it
arrived in.

## Options considered

**A. Accept it; the corpus says these confirmations are correct.**
Rejected. They are correct on 35 fixtures written by us. They are correct
*because* the corpus's genuine notices happen to look genuine structurally. The
first well-made scam in the wild inverts this, and it inverts it silently.

**B. Cap Tier-0 supporting strength so it cannot reach the TRUE band.**
Tried, and it worked — at the calibrated scale. Then rejected. The cap only
holds for particular values of `log_odds_per_unit_strength`: at scale 4.5 a cap
of 0.20 still lands at p = 0.18, inside TRUE. The protection would silently
switch off the next time the scale was recalibrated, and nothing would fail.
A safety property that depends on an unrelated tuning constant is not a safety
property.

**C. Make confirmation a structural requirement of the label.**
Chosen.

## Decision

`TRUE` requires at least one piece of `status=ok, signal=supports` evidence from
an agent in `verdict.confirming_agents` — currently `InstitutionalSource` and
`OfficialChannel`, the two agents that actually go and look at a source
entitled to publish the notice.

If the arithmetic lands in TRUE territory and no such evidence exists, the label
becomes `UNVERIFIED` and `Aggregation.downgraded_for_lack_of_confirmation` is
set so the UI can say why.

Every other label remains purely arithmetic. **Only TRUE is privileged**,
because only TRUE is a positive claim about the world that the accumulated
evidence does not actually contain.

The same reasoning is applied a second time to ADR-0026. `StrainPrior` is listed
in `verdict.cannot_conclude_alone`: if the only usable evidence comes from
agents that observed something at *another* institution, the answer is
UNVERIFIED regardless of the posterior. One campus's mistake must not become
every campus's verdict, and a poisoned strain at one college must not be able to
convict a genuine notice at another. Again, structural rather than a cap.

## Consequences

- Tier 0 alone can **condemn but never confirm**. Measured on the corpus: 12/13
  scams caught, 0/14 genuine notices confirmed, 0 libelled. This is the honest
  shape of what a rule engine knows.
- The offline demo claim narrows and gets more truthful: with the network
  unplugged, HERD still catches the scam. It does not pretend to verify the
  genuine notice, because verifying one requires a source it cannot reach.
- `UNVERIFIED` becomes the correct and common Tier-0 answer for genuine
  notices, which is why the abstention target in `thresholds.yaml` applies to
  the full cascade rather than to Tier 0 in isolation.
- Adding a new agent that is entitled to confirm requires an explicit edit to
  `verdict.confirming_agents`. That is intentional friction: entitlement to
  confirm is a claim about what an agent can actually see.

## Consequence accepted

The system will say "I could not verify this" about notices that are perfectly
genuine, whenever the institution has not published them anywhere reachable.
That is a real cost, paid by the people whose genuine notice gets a hedge
instead of a green tick.

It is the right cost. The alternative is a system that says "verified" because
nothing looked wrong, which is the exact reasoning that makes a well-made scam
work in the first place.
