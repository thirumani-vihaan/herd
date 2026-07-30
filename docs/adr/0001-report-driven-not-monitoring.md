# ADR-0001 — Report-driven ingestion, never group monitoring

**Status:** Accepted

## Context

To model how fast a rumour is spreading, we need observations of it spreading.
The richest possible data source would be the group chats themselves.

## Options

**A. Monitor group chats.** Join groups via a bot or use an unofficial client.
Gives true message counts, real timestamps, actual network topology, and would
make the spread model dramatically better.

**B. Platform partnership.** Ask WhatsApp/Meta for aggregate forwarding signals.
Not available to anyone at this scale; also unavailable in principle for
end-to-end encrypted content.

**C. Report-driven.** Only see what a human explicitly submits.

## Decision

**C — report-driven only.** HERD does not join, read, subscribe to, or scrape any
chat.

## Reasoning

Option A is a trap that looks like an advantage. It requires the tool to ingest
every message from people who never consented — including the private
conversations of everyone in the group. A system built to protect people from
having their trust exploited cannot be built on exploiting their trust. It is
also the property that would make institutional adoption impossible: no college
will authorise a bot that reads student group chats, and no student should accept
one.

The decisive practical point is that the behaviour we need **already exists**.
People already screenshot suspicious messages and forward them to a friend asking
"is this real?" HERD intercepts a habit rather than creating one, which is why
adoption does not require behaviour change.

## Consequences

**Accepted costs:**
- Report counts are a biased proxy for true spread, requiring the explicit
  observation model in [ADR-0018](0018-report-process-bias.md).
- No social graph, so targeting is cohort-level rather than individual
  ([Intervention](../05-intervention.md)).
- Cold start is real: with no reporters there is no signal.

**Gained:**
- Legally and ethically deployable without institutional negotiation.
- Nothing sensitive to leak, because nothing sensitive is collected.
- Brigading cannot corrupt verdicts, only timing — see
  [Trust & safety](../06-trust-and-safety.md).

This constraint is permanent. It is not revisited when the spread model would
benefit from better data.
