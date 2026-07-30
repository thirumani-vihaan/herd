# ADR-0019 — Expected-harm alert rule, not fixed thresholds

**Status:** Accepted — supersedes `if confidence > θ and velocity > k`

## Context

When should HERD fire an alert? This is the system's central decision — everything
upstream exists to inform it.

The initial design used a threshold: alert when confidence exceeds a bar and the
current time is sufficiently before the projected peak.

## Options

**A. Fixed thresholds.** Simple, tunable, and with no principled setting. It fails
in both directions: it fires on a dying rumour that happens to have high
confidence, and stays silent on an explosive one at moderate confidence — because
a threshold cannot express that those two situations differ in *stakes* rather
than in *certainty*.

**B. Expected-harm maximisation.** Decision-theoretic. Requires estimating several
quantities.

**C. Learned policy.** Needs outcome data that does not exist yet.

## Decision

**B.** Fire at the time maximising expected harm prevented, when that quantity is
positive.

```
E[prevented | alert at t]
  = P(false) × unreached(t) × P(acts | exposed) × harm_per_action × efficacy(t)

E[cost | alert at t]
  = P(true) × trust_damage  +  fatigue_cost(recent_alerts)
```

## Reasoning

The decisive argument is that the right behaviours **fall out** of B, whereas each
would have to be hand-tuned into A, and several cannot be expressed in A at all:

| Behaviour | Why it emerges |
|---|---|
| Alert early | `unreached(t)` decreases monotonically, so delay costs reach |
| Don't alert a dead rumour | `unreached ≈ 0` ⇒ nothing left to prevent, regardless of confidence. **A threshold rule cannot express this.** |
| Higher bar for low-stakes claims | `harm_per_action` scales with money at risk — a ₹750 fee clears sooner than a venue change |
| Fatigue suppression | It is a cost *term*, so the Nth alert this week automatically faces a higher bar |
| Don't alert after the peak | `efficacy(t)` decays once belief has formed — the pre-bunking finding, priced in |

The second row is the clearest failure of A. A fixed-threshold system will
confidently alert on a rumour that has already finished spreading, because it has
no representation of "there is no one left to warn". That alert is pure cost: it
spends fatigue budget and delivers zero prevention.

`efficacy(t)` is where the inoculation literature enters the arithmetic rather than
sitting in a design rationale. Because inoculation before exposure substantially
outperforms correction after belief formation
([ADR-0020](0020-prebunk-framing.md)), the value of an alert genuinely collapses
after the peak — and the decision rule should reflect that, not merely the
documentation.

## Consequences

**Accepted costs:**
- Several quantities must be estimated, and `P(acts | exposed)` is initially a
  prior rather than a measurement. It is stated as an assumption in the alert
  record and refined from feedback data.
- Harder to explain than "confidence > 0.8". Mitigated by showing the computed
  expected-harm value on the alert record.
- Requires the spread model to produce `unreached`, with all the caveats of
  [ADR-0018](0018-report-process-bias.md).

**Gained:**
- Alert timing is a principled decision with a stated objective.
- Fatigue is priced rather than bolted on.
- The system does not waste trust on rumours that are already over.
- `lead_time_hours` becomes a real scorecard: a system alerting after the peak has
  measurably failed at its only job.
