# ADR-0017 — Sample-size-tiered spread model

**Status:** Accepted — supersedes "fit SEIR"

## Context

The initial design specified fitting an SEIR model to report timestamps via
`scipy.optimize.curve_fit`.

SEIR has four compartments and at least two free parameters. Fitting it to the
eleven data points a strain typically has when a decision is needed is not
modelling — it is numerology dressed as rigour. The fit will converge on
*something*, the chart will look authoritative, and the numbers will be
meaningless. Worse, the failure is invisible: nothing errors, and the output looks
exactly like a real result.

## Options

**A. Always SEIR.** Impressive-looking, unjustifiable at realistic n.

**B. Always simple exponential.** Honest, but wastes real information once a
strain has hundreds of reports.

**C. Tiered by sample size**, with the model in use displayed alongside the curve.

**D. Always Hawkes process.** Theoretically the most correct model for a
self-exciting forwarding cascade, but unstable at small n and much harder to
explain.

## Decision

**C.**

| n reports | Model | Reports | Display |
|---|---|---|---|
| 1–4 | none | count, inter-arrival times | "insufficient data to project" |
| 5–20 | Bayesian exponential | doubling time + credible interval | wide band |
| 21–60 | logistic | inflection, saturation | band |
| > 60 | SEIR / Hawkes | R estimate, peak interval | band |

**The system never upgrades to a richer model because it looks better on screen.**
The model in use is rendered next to the curve, and `caveats` are shown verbatim.

## Reasoning

The model must be justified by the data, not by the aesthetics of the output. A
tiered estimator makes the honesty structural rather than a matter of discipline —
there is no code path that fits SEIR to seven points.

**Why Bayesian at small n.** Least squares on seven points returns a point
estimate with no meaningful error bar. A Bayesian fit with a weakly-informative
prior returns a posterior whose *width is the answer*: "doubling somewhere between
every 40 minutes and every 6 hours" is genuinely actionable — it says "I have
hours, not days" — while a false-precision point estimate invites a decision the
data cannot support.

**Why Hawkes is kept in the top tier.** Forwarding is a self-exciting point
process; each forward raises the short-term probability of more. Hawkes models
that literally, and its branching ratio is the honest analogue of R₀ for an
information cascade. SEIR's compartments are a metaphor here — but a *useful*
one, because the `Exposed` compartment names the exact population the intervention
targets: people who have seen it and not yet acted. Keeping both means using
Hawkes for velocity and SEIR for the quantity being raced.

## Consequences

**Accepted costs:**
- Four estimators to implement and test rather than one.
- Early in a strain's life the system openly says it cannot project. That is the
  correct answer and it must survive the temptation to fill the space.
- `curve_fit` failures must be caught and reported as "insufficient data" — never
  allowed to crash, never allowed to fabricate.

**Gained:**
- Every displayed number is supportable by the data behind it.
- The visible model label and caveats make the system's own uncertainty legible.
- Under scrutiny, this is defensible rather than merely impressive.
