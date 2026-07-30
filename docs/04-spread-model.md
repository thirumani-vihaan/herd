# Spread Model

This is the part of HERD most likely to be over-claimed, so this document leads
with the limitation rather than burying it.

## What we are actually observing

HERD does not observe the epidemic. It observes **reports about the epidemic**,
and reports are a heavily biased sample:

- Only people who *doubted* the message report it. The population most at risk —
  those who believed it — is systematically absent from the data.
- Reporting propensity is not constant. It spikes when someone influential says
  "guys check this", and it decays as the rumour becomes old news.
- Reports arrive later than exposures, with a variable lag.

Any model that treats report counts as infection counts is measuring the wrong
process and will produce confident nonsense.

## The honest formulation

Let `I(t)` be true cumulative exposure and `Y(t)` observed reports. We model

```
Y(t) ~ Poisson( ρ(t) · I(t - λ) )
```

- `ρ(t)` — reporting rate, the fraction of exposed people who report
- `λ` — reporting lag

We cannot identify `ρ` and `I` separately from report data alone; that is a
genuine identifiability problem, not a modelling oversight. Two things rescue it:

1. **We do not need the level, only the shape.** The intervention decision
   depends on *growth rate* and *time to peak*, and if `ρ` is roughly
   stationary over the window of interest, the growth rate of `Y` is an unbiased
   estimator of the growth rate of `I` even though the level is not.
2. **`λ` is partially observable.** Screenshots carry the original message
   timestamp in the UI chrome. Using *message* time rather than *report* time
   removes most of the lag and is the single highest-value signal the ingestion
   layer extracts ([ADR-0018](adr/0018-report-process-bias.md)).

Everything downstream is stated in terms of growth and timing, never in terms of
"how many people were fooled". Where a reach figure is displayed at all, it is an
interval with an explicit assumption label attached.

---

## Tiered estimation

Fitting a four-compartment SEIR model to eleven data points is numerology. The
estimator therefore switches on sample size ([ADR-0017](adr/0017-tiered-spread-model.md)):

| n reports | Model | Reports | Displayed as |
|---|---|---|---|
| 1–4 | none | count and inter-arrival times only | "insufficient data to project" |
| 5–20 | Bayesian exponential growth | doubling time with credible interval | wide band |
| 21–60 | logistic | inflection point, saturation estimate | band |
| > 60 | SEIR / Hawkes | R estimate, peak interval | band |

The system **never** upgrades to a richer model just because it looks better on
screen. The model in use is displayed on the dashboard next to the curve, and the
`caveats` list is rendered verbatim.

### Why Bayesian at small n

A least-squares exponential fit on seven points returns a point estimate with no
honest error bar. A Bayesian fit with a weakly-informative prior on growth rate
returns a posterior whose width *is* the answer — "somewhere between doubling
every 40 minutes and every 6 hours" is genuinely actionable ("I have hours, not
days") while a false-precision point estimate is not.

### Why Hawkes is considered at all

Forwarding is a self-exciting point process: each forward raises the short-term
probability of further forwards. A Hawkes process models this directly, and its
branching ratio `n*` is the natural analogue of R₀ for information cascades.
SEIR's compartments are a metaphor here; Hawkes is the literal model.

We keep both because they answer different questions. Hawkes gives the better
short-horizon velocity estimate; SEIR's `Exposed` compartment gives the quantity
the intervention actually targets — **people who have seen it but not yet acted**.
That population is the entire point of the system, and it is the thing HERD is
racing.

---

## From estimate to decision

The alert rule is **not** `if confidence > 0.8 and velocity > k`. Fixed thresholds
have no principled setting and fail in both directions — they fire on a dying
rumour with high confidence and stay silent on an explosive one with moderate
confidence.

Instead, alerting maximises expected harm prevented
([ADR-0019](adr/0019-expected-harm-alerting.md)):

```
E[harm prevented | alert at t]
    = P(false) × unreached(t) × P(acts | exposed) × harm_per_action × efficacy(t)

E[cost | alert at t]
    = P(true) × trust_damage  +  fatigue_cost(recent_alert_count)
```

Fire when the difference is maximised and positive. The consequences fall out
naturally rather than being tuned in:

- **Alert early.** `unreached(t)` shrinks monotonically, so waiting costs reach.
- **Do not alert a dead rumour.** If `unreached` is near zero, there is no harm
  left to prevent regardless of how certain we are.
- **Higher bar for higher-stakes claims.** `harm_per_action` scales with the money
  at risk — a ₹750 registration fee clears the bar sooner than a "fest venue
  changed" rumour.
- **Fatigue is priced in**, not bolted on. Each recent alert raises the cost term,
  so the Nth alert this week must clear a higher bar than the first.

`efficacy(t)` encodes the pre-bunking finding that inoculation before exposure
substantially outperforms correction after belief has formed
([Intervention](05-intervention.md)) — which is precisely why the term decays
sharply after the peak.

---

## Displayed metrics

Three numbers appear on the dashboard, chosen because they are the three a person
can actually act on:

1. **Doubling time** (with interval) — "how much time do I have"
2. **Lead time** — hours between alert firing and projected peak. This is HERD's
   own scorecard: a system that alerts after the peak has failed at its one job.
3. **Unreached estimate** (with interval) — how much harm is still preventable

The epidemic curve renders observed reports, the fitted model with its credible
band, the projected peak interval, and a clearly marked line where the alert
fired. If the alert line is not visibly left of the peak band, the system is
failing and the chart should show that plainly rather than hide it.
