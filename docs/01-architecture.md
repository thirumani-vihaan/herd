# Architecture

## Shape of the system

HERD is a streaming pipeline with a memory. Reports arrive continuously; each one
is either recognised (cheap) or investigated (expensive); recognised reports feed
a spread model that decides *when* to intervene.

```
 INGEST            PERCEIVE           RECOGNISE            INVESTIGATE
 ------            --------           ---------            -----------
 web + QR   -->    OCR          -->   strain match   -->   Tier 0  rules
 telegram          claim              (vector)             Tier 1  lookups
 share-intent      extraction              |               Tier 2  retrieval
                                           |               Tier 3  synthesis
                                      hit  |  miss                 |
                                           |                       |
                                           v                       v
                                    +--------------------------------+
                                    |          VERDICT STORE          |
                                    |  label + confidence + evidence  |
                                    +----------------+----------------+
                                                     |
                                MODEL                v            INTERVENE
                                -----      +-------------------+  ---------
                                           |   spread model    |
                                           | velocity, R, peak |
                                           +---------+---------+
                                                     |
                                            expected-harm rule
                                                     |
                                                     v
                                          pre-bunk to unreached
```

The load-bearing idea is the **recognise** stage. A rumour is a template that
gets resent thousands of times with small mutations. If report #1 is investigated
properly and reports #2..#N are matched to it in milliseconds, then the marginal
cost of an attack's success collapses toward zero — the wider it spreads, the
cheaper it becomes to neutralise.

## Layers

### 1. Ingest
Three doors, one normalised `Report`. Screenshot is the primary modality because
that is how forwards actually travel — people screenshot and resend rather than
copy text. See [ADR-0002](adr/0002-screenshot-first-input.md), [ADR-0003](adr/0003-ingestion-channels.md).

Reporters are pseudonymous by construction ([ADR-0004](adr/0004-pseudonymous-reporters.md)).

### 2. Perceive
Multimodal LLM performs OCR and claim extraction in a single pass
([ADR-0005](adr/0005-multimodal-ocr.md)) — separating them loses layout and
emoji context that matter for code-mixed South Indian group chat. Output is a
schema-validated `Claim`.

### 3. Recognise
Multilingual embedding ([ADR-0006](adr/0006-multilingual-embeddings.md)) +
incremental nearest-strain assignment ([ADR-0007](adr/0007-incremental-strain-assignment.md)).
Strain identity requires *both* semantic similarity and entity compatibility
([ADR-0008](adr/0008-strain-identity.md)) — otherwise two different companies'
scams collapse into one strain because the template text is identical.

### 4. Investigate
A four-tier cascade, not a parallel broadcast ([ADR-0011](adr/0011-tiered-investigation-cascade.md)).
Agents return evidence with sources, never verdicts ([ADR-0012](adr/0012-evidence-not-verdicts.md)).
The label is set by deterministic aggregation; the LLM only writes the prose
([ADR-0013](adr/0013-deterministic-verdict-aggregation.md)).

### 5. Model
Spread estimation is tiered by sample size ([ADR-0017](adr/0017-tiered-spread-model.md))
and explicitly corrects for the fact that reports are a biased sample of true
spread ([ADR-0018](adr/0018-report-process-bias.md)).

### 6. Intervene
Alert timing is an expected-harm decision, not a fixed threshold
([ADR-0019](adr/0019-expected-harm-alerting.md)). Messages are framed as
inoculation rather than correction ([ADR-0020](adr/0020-prebunk-framing.md)).

## Latency budget

The demo and the product both live or die on these numbers.

| Path | Budget | Where it goes |
|---|---|---|
| **Recognised report** (cache hit) | **< 300 ms** | embed 40 ms, vector search 15 ms, entity check 5 ms, render 200 ms |
| **New strain, Tier 0 conclusive** | **< 2 s** | + rule engine 30 ms, LLM prose 1.5 s |
| **New strain, full cascade** | **< 20 s** | + parallel lookups 3 s, retrieval 2 s, synthesis 4 s, slack 10 s |
| Alert fan-out | < 1 s | WebSocket broadcast + Telegram batch |

Cache-hit latency is the headline metric. It should be displayed live.

## Failure model

Every external dependency is wrapped by a `Resilient` decorator providing
timeout → retry-with-jitter → cassette fallback → graceful skip. An agent that
fails does **not** fail the investigation; it contributes an `Evidence` record
with `status=unavailable`, and the aggregator widens its uncertainty accordingly.

| Dependency | Fails how | Consequence |
|---|---|---|
| LLM API | timeout / quota | cassette in replay mode; otherwise degrade to Tier 0 rules only, label `UNVERIFIED` |
| Embedding model | n/a — runs locally | none |
| Vector store | disk | in-memory fallback, warn |
| RDAP / Safe Browsing | rate limit | evidence marked unavailable, confidence widens |
| Institutional site | down | pre-crawled snapshot ([ADR-0015](adr/0015-institutional-snapshot.md)) |
| Telegram | outage | WebSocket page still updates |

**Invariant:** the system never blocks on an external call and never emits a
confident verdict built on unavailable evidence.

## Deployment

v1 is a single process plus a static frontend ([ADR-0022](adr/0022-single-process-v1.md)).
SQLite for relational state, on-disk vector index, in-process async task queue.
This is deliberate: distributed infrastructure buys throughput HERD does not yet
need, and costs reliability HERD cannot afford.

The interfaces (`TaskQueue`, `VectorIndex`, `Store`) are abstract so the swap to
Redis/Qdrant/Postgres is a config change when a second campus arrives.

## Replay mode

`DEMO_MODE=replay` routes every network call through a cassette recorded on a
prior live run ([ADR-0023](adr/0023-cassette-replay.md)), preserving original
latencies so the timing of the demo is unchanged. The system is fully functional
with the network physically disconnected. This is a correctness feature, not a
demo trick — it is also how the integration tests run in CI.
