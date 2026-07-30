# ADR-0021 — Telegram and WebSocket as primary delivery; Web Push best-effort

**Status:** Accepted — supersedes "Web Push notifications"

## Context

An alert that is not delivered prevents nothing. The initial design specified Web
Push as the delivery mechanism for inoculation cards.

Web Push is the wrong primary channel:

- **iOS support is conditional.** Safari requires the site to be installed to the
  home screen before push works at all — an install step, which is exactly the
  friction [ADR-0003](0003-ingestion-channels.md) removed from the input path.
  Reintroducing it on the output path defeats the point.
- **The permission prompt is declined by most users**, and once declined it is
  effectively unrecoverable.
- **Delivery is not observable.** Push services do not reliably report delivery,
  so the system cannot know whether it reached anyone — which makes the reach
  metrics in [Evaluation](../07-evaluation.md) unverifiable.

A delivery channel whose success cannot be measured is not a delivery channel.

## Options

**A. Web Push primary.** Zero install in theory, unreliable in practice.
**B. Telegram bot primary.** Reliable, observable, requires Telegram.
**C. SMS.** Universal, costs money, needs phone numbers — which
[ADR-0004](0004-pseudonymous-reporters.md) refuses to store.
**D. Live WebSocket page.** Instant and certain for anyone with the page open;
useless when it is closed.
**E. Layered: B + D primary, A best-effort, email as slow backstop.**

## Decision

**E.**

| Channel | Reliability | Role |
|---|---|---|
| Telegram bot | very high | Primary. Anyone who reported via Telegram is reachable with certainty, and delivery is confirmable. |
| WebSocket page | very high | Primary. Instant for anyone with the page open. |
| Web Push | medium | Best-effort upgrade where supported. |
| Email digest | high, slow | Daily summary; never time-critical. |

## Reasoning

The layering is chosen so that **no single channel failing reduces delivery to
zero**, and so that at least one channel gives *confirmable* delivery. Telegram
provides the second property, which is what makes reach measurable rather than
assumed.

C is rejected on a structural ground rather than a cost one: it requires storing
phone numbers, which contradicts the pseudonymity guarantee. A privacy property
that is abandoned the moment it becomes inconvenient was never a property.

The pairing of B and D is also what makes the system's key moment work: a room of
people who submitted via the QR page see the card appear on their screens
simultaneously over WebSocket, while Telegram subscribers get it as a push. Two
independent mechanisms, neither dependent on a permission prompt.

## Consequences

**Accepted costs:**
- Telegram reach is limited to Telegram users, which is not universal in this
  population.
- WebSocket reach requires the page to be open.
- Four delivery paths to implement and test.

**Gained:**
- No dependency on a permission prompt for the primary path.
- Delivery is confirmable, so reach metrics are real.
- Graceful degradation: a failing channel reduces reach rather than breaking
  delivery.

**Revisit when:** WhatsApp Business API approval lands, at which point it becomes
the highest-reach channel and likely the primary one.
