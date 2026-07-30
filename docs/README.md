# HERD — Design Documentation

## Reading order

| # | Document | Read it for |
|---|---|---|
| 1 | [Architecture](01-architecture.md) | The shape of the system, dataflow, latency budget, failure model |
| 2 | [Data model](02-data-model.md) | Every entity and schema in the pipeline |
| 3 | [Investigation](03-investigation.md) | How a claim becomes cited evidence |
| 4 | [Spread model](04-spread-model.md) | The epidemiology, and where it's honest about its limits |
| 5 | [Intervention](05-intervention.md) | Pre-bunking, targeting, delivery |
| 6 | [Trust & safety](06-trust-and-safety.md) | False positives, abuse, privacy, liability |
| 7 | [Evaluation](07-evaluation.md) | How we know it works |
| 8 | [API](08-api.md) | HTTP and WebSocket surface |
| 9 | [Non-goals](09-non-goals.md) | What HERD deliberately refuses to do |

## Architecture Decision Records

Every significant fork is recorded in [`adr/`](adr/) with the options considered,
the tradeoff, the decision, and the consequences we accept.

Start with [`adr/README.md`](adr/README.md) for the index.

## The one paragraph that explains the whole system

Fact-checking answers *"is this true?"* — a question that arrives too late,
because the person who bothered to ask was never the one at risk. The people who
get hurt are the ones who never doubted it. So HERD answers a different question:
**how fast is this spreading, who hasn't been reached yet, and can I get there
first?** That reframes misinformation from a classification problem into an
interception problem, which is why the system is built out of epidemiology and
scheduling rather than out of a better classifier.

## Design principles

These are the tiebreakers. When two options are close, the one that better
satisfies a principle higher in this list wins.

1. **Never assert what you cannot cite.** Every verdict carries sources with
   timestamps. Confidence is calibrated, and `UNVERIFIED` is an honourable
   outcome rather than a failure.
2. **Determinism where it matters.** LLMs are used for perception and language,
   never for the final label. See [ADR-0013](adr/0013-deterministic-verdict-aggregation.md).
3. **Cheap before expensive.** The investigation is a cascade, not a broadcast.
   Most reports must cost near-zero. See [ADR-0011](adr/0011-tiered-investigation-cascade.md).
4. **Consent over surveillance.** HERD only ever sees what a human hands it. It
   does not join groups, read chats, or monitor anyone.
5. **Degrade, never disappear.** Every external dependency has a fallback. The
   system runs with the network unplugged.
6. **Be wrong out loud.** Every verdict publishes what would change its mind.
