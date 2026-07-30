# Intervention

Detection without delivery is a dashboard. This layer is where HERD either
changes an outcome or does not.

## Why pre-bunking rather than debunking

The intervention is designed around one robust finding from inoculation theory
(McGuire; Roozenbeek & van der Linden): **warning people before exposure, and
showing them the manipulation technique in weakened form, confers durable
resistance** — while correction after a belief has formed is weak, and can
entrench the belief in some populations.

This is not a stylistic preference; it determines the architecture. If correction
worked well, HERD would only need to be *accurate*. Because inoculation works and
correction largely does not, HERD must be *early* — which is why an entire
spread-modelling layer exists to buy lead time
([ADR-0020](adr/0020-prebunk-framing.md)).

The message therefore reads *"you may soon receive…"* rather than *"that message
you saw was fake."* For anyone not yet exposed — the target population — the
first is inoculation and the second is irrelevant.

## The inoculation card

Deliberately small. A wall of text is not read on a phone.

```
+--------------------------------------------------+
|  HEADS UP — spreading in your college now        |
|                                                  |
|  You may soon receive a message about an         |
|  "Amazon off-campus drive" asking for a ₹750     |
|  registration fee.                               |
|                                                  |
|  Two things we checked:                          |
|  • Amazon's careers page lists no such drive     |
|  • The link's domain was registered 4 days ago   |
|                                                  |
|  The technique: real employers never charge      |
|  candidates. A fee request is the tell.          |
|                                                  |
|  Already paid? Tap here.        [ see evidence ] |
+--------------------------------------------------+
```

Five deliberate choices:

1. **Exactly two pieces of evidence** — the strongest supporting and the most
   independent. More reads as pleading; fewer reads as assertion.
2. **Names the technique, not just the instance.** "A fee request is the tell" is
   the part that transfers to the next scam, which is the entire mechanism of
   inoculation. Without it we have blocked one attack instead of building
   immunity.
3. **An action path for people already harmed.** They are the most motivated
   readers and the most likely to warn others; ignoring them wastes the strongest
   available amplifier.
4. **Evidence is one tap away, never inline.** Trust requires that the evidence
   be *available*, not that it be *read*.
5. **No accusatory language.** "We could not verify, and here are the signals" —
   never "scam". See [Trust & safety](06-trust-and-safety.md).

## Targeting

Two audiences, chosen by the expected-harm calculation:

| Audience | When | Why |
|---|---|---|
| **Predicted path** | high velocity, well-defined affected cohort | Reaches the unreached without spending fatigue budget on everyone else |
| **All subscribers** | high harm, broad claim, or ambiguous cohort | Coverage is worth the fatigue cost |

"Predicted path" is inferred *only* from cohort attributes that reporters
volunteered (year, branch) — never from a social graph, because HERD does not
have one and building one would require exactly the surveillance the system
refuses ([ADR-0001](adr/0001-report-driven-not-monitoring.md)).

This is a real capability limit, stated plainly: HERD can target a cohort but not
an individual's network position. It buys the ability to target at all without
paying for it in surveillance.

## Channels

Delivery is where the first design was weakest — it assumed Web Push, which is
unreliable on iOS and requires a permission prompt most users decline
([ADR-0021](adr/0021-intervention-channels.md)).

| Channel | Reliability | Role |
|---|---|---|
| **Telegram bot** | very high | Primary. Anyone who reported via Telegram is reachable with certainty. |
| **Live WebSocket page** | very high | Anyone with the page open sees the card appear instantly. |
| **Web Push** | medium | Best-effort upgrade where the browser supports it. |
| **Email digest** | high, slow | Daily summary; not for time-critical alerts. |

The system never depends on a single channel, and a channel failing degrades
reach rather than breaking delivery.

## Fatigue

An alerting system that cries wolf is worse than no system, because it trains its
audience to ignore the one alert that mattered.

- Fatigue is priced into the alerting decision as a cost term, so suppression is
  a consequence of the same rule that fires alerts, not a separate hack
  ([Spread model](04-spread-model.md)).
- Hard ceiling per user per week regardless of the calculation, as a backstop.
- Mutations of an already-alerted strain **update the existing card** rather than
  sending a new one — this is a direct payoff of strain identity being modelled
  properly.
- Users choose a threshold: everything, or high-harm only.

## Closing the loop

Every card carries a one-tap "was this useful?" and, where relevant, "I had
already seen this." Both feed evaluation:

- *Already seen* is a direct measure of how much lead time was actually
  delivered, and is the only unbiased estimate of `ρ`, the reporting rate, that
  the system can obtain ([Spread model](04-spread-model.md)).
- *Not useful* on a `TRUE`-labelled claim is a false-positive signal that routes
  straight to review.

The intervention layer is therefore also the measurement layer. Without it the
spread model would have no ground truth about its own reach.
