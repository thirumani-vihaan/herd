# ADR-0018 — Model the report process explicitly; prefer message time

**Status:** Accepted

## Context

HERD observes reports, not infections. Treating report counts as infection counts
is the single most likely way for this system to produce confident nonsense, and
it is the standard mistake in this class of tool.

Two distinct problems:
1. **Selection bias** — only people who *doubted* the message report it. The
   population most at risk, those who believed it, is systematically absent.
2. **Observation lag** — a report arrives some time after the exposure that caused
   it, with variable delay.

## Options

**A. Ignore it.** Treat reports as infections. Simple, and wrong in a way that is
invisible until someone asks.

**B. Model reports as a thinned, delayed observation of true spread**, and only
report quantities that survive the unidentifiability.

**C. Estimate the reporting rate from an external survey.** Not available.

## Decision

**B**, with two concrete mechanisms.

### 1. State the observation model, and only claim what it supports

```
Y(t) ~ Poisson( ρ(t) · I(t - λ) )
```

`ρ` (reporting rate) and `I` (true exposure) are **not separately identifiable**
from report data alone. This is acknowledged rather than papered over. The
consequence is enforced downstream: the system reports **growth and timing**, which
survive an unknown constant `ρ`, and never reports **levels** as if they were
measured. Any reach figure displayed at all is an interval with its assumption
labelled.

### 2. Use message time, not report time

Screenshots carry the original message timestamp in the platform's UI chrome. When
`ForwardMarkers.visible_timestamp` is present, the spread model uses it instead of
`received_at`, which removes most of `λ`.

**This is the single highest-value signal the ingestion layer extracts**, and it
is the concrete reason [ADR-0002](0002-screenshot-first-input.md) chose
screenshot-first input. A text-first pipeline has no access to it.

## Reasoning

The identifiability problem is real and cannot be solved with better fitting; it
can only be respected. Respecting it means being disciplined about which
quantities leave the model. Growth rate is invariant to a constant `ρ`, so it is
reportable. Absolute exposure is not, so it is not.

The `Interval` type in the data model enforces this at the schema level: projected
quantities are typed such that no display code can accidentally render a point
estimate. Making the honesty a type rather than a convention is what makes it
survive the pressure to show a cleaner number.

The one signal that *does* constrain `ρ` comes from the intervention layer:
"I had already seen this" feedback on inoculation cards is an unbiased sample of
exposure among the reachable population. It is the only route to validating the
model's assumptions in production rather than in backtest, which is why the
feedback control exists ([Intervention](../05-intervention.md)).

## Consequences

**Accepted costs:**
- The system cannot say "1,400 students were exposed". It says "spreading with a
  doubling time between 40 minutes and 6 hours".
- Message-time extraction depends on OCR reading UI chrome, which fails on
  cropped screenshots. Falls back to report time with widened intervals.
- More conservative-looking output than a naive system would produce.

**Gained:**
- Every claim survives a statistician's question.
- Lag is materially reduced where the screenshot allows it, which directly
  increases usable lead time.
- The one place the model could be dishonest is closed by the type system.
