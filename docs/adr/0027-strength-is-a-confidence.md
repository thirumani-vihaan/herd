# ADR-0027: Evidence strength is a confidence, not a log-odds delta

**Status:** Accepted
**Date:** During P5 (investigation layer)
**Supersedes:** nothing. Fixes an arithmetic bug in the ADR-0013 aggregator.

## Context

ADR-0013 specifies aggregation in log-odds:

```
log_odds = logit(prior) + Σ direction × strength × reliability
```

`Evidence.strength` is documented as a 0..1 confidence, and the fraud rule set
assigns `upfront_fee_for_job` a strength of 0.85 with the rationale
"legitimate employers do not charge candidates — near-conclusive".

When the first end-to-end Tier-0 run was measured against the labelled corpus,
**every single one of the 35 fixtures came back UNVERIFIED**, including the
flagship scam that trips six independent fraud rules.

The arithmetic was working exactly as written, and that was the problem. Adding
a strength directly to a log-odds accumulator implicitly asserts that a
strength of 1.0 means a likelihood ratio of e ≈ 2.7. The prior sits at
logit(0.35) = −0.62 and the FALSE band begins at logit(0.90) = +2.20, so
reaching FALSE requires a total delta of 2.82. With every agent capped at 1.0
and only nine agents in the system — most of which are correlated, capped
further, or neutral on any given claim — **no achievable combination of
evidence could reach the FALSE band**. The verdict bands in
`config/thresholds.yaml` described a region the system could not enter.

This is a particularly dangerous class of bug: nothing raised, nothing logged,
every unit test on the aggregator's *mechanics* passed, and the output was
superficially reasonable — a cautious system that abstains a lot. It was only
visible by measuring label distribution against ground truth.

## Options considered

**A. Raise the strengths in `fraud_rules.yaml` to log-odds magnitudes.**
Rejected. It conflates two different quantities in one field: how sure the rule
is, and how much that should move a posterior. Reviewers of the rule file would
have to think in log-odds to sanity-check a rule, and `Evidence.strength`
returned by a future LLM-backed agent would have no natural scale.

**B. Lower the verdict bands until the reachable range covers them.**
Rejected outright. The bands are calibrated statements about acceptable error
rates. Moving them to fit broken arithmetic would mean the system declares FALSE
at a genuine posterior of 0.6 while the UI prints 0.9.

**C. Introduce an explicit conversion from confidence to log-odds.**
Chosen. `strength` stays a readable 0..1 confidence; a single calibrated
constant, `aggregation.log_odds_per_unit_strength`, converts it. The two
quantities stay separate and each is independently reviewable.

## Decision

Add `aggregation.log_odds_per_unit_strength` and multiply every contribution by
it. Add `aggregation.agent_saturation`, the total raw rule weight at which a
single agent reports strength 1.0, so that an agent aggregating many rules has
a principled way to express "as sure as I can be".

Both constants are calibrated by `tools/calibrate_aggregation.py` against the
labelled corpus, never chosen by eye.

## Constraint discovered during calibration

The search initially preferred the largest scale on offer, because a larger
scale pushes every correct answer further from the decision boundary and so
scores better on worst-case margin. That optimum is degenerate: at a scale of
7.0, **one agent at full strength contributes 7.0 log-odds against a clamp of
±6.0**, so it alone exhausts the entire confidence budget and every other
agent's evidence is arithmetically discarded. A nine-agent cascade in which one
agent decides everything is not a cascade.

The calibrator therefore enforces `scale × 2 ≤ max_abs_log_odds` — at least two
full-strength agents are required to reach the clamp. This is the weakest
statement of "this is a multi-agent system" that is still true, and
`tests/test_aggregate.py::test_no_single_agent_can_exhaust_the_confidence_budget`
asserts it against the shipped config rather than against the calibrator's
memory of it.

## Consequences

- Two more calibrated constants, and two more things that must be re-derived
  when the rule set changes. `tools/calibrate_aggregation.py` is the only
  sanctioned way to change them.
- `Aggregator.from_thresholds` becomes the single construction site, so a new
  knob cannot be wired into one caller and forgotten in another.
- The calibrated scale (3.0) sits exactly at the multi-agent bound. Raising
  `max_abs_log_odds` would relax it; that would be a separate decision about how
  certain the system is ever allowed to be, and it is not being made here.

## What this bug taught

The aggregator had thorough unit tests before this was found, and all of them
passed. They tested that caps applied, that correlated signals were discounted,
that the clamp clamped — every mechanism in isolation, correctly. None of them
asked the only question that mattered: *can this system, as configured, ever
actually reach the verdicts it claims to produce?*

Hence `tests/test_aggregate.py` now contains corpus-level tests that assert
reachability and outcome distribution, not just mechanism.
