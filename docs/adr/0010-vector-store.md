# ADR-0010 — Chroma as the vector index, behind an interface

**Status:** Accepted

## Context

Strain matching needs nearest-neighbour search over claim embeddings, on the hot
path for every report.

## Options

| | Pros | Cons |
|---|---|---|
| **A. FAISS** | Fastest, battle-tested | No persistence layer or metadata filtering — both must be built |
| **B. Chroma** | Persistence, metadata filters, trivial local setup | Slower; API has drifted across versions |
| **C. Qdrant** | Excellent filtering and performance | Separate server process |
| **D. `sqlite-vec`** | One file, no extra service | Young; smaller ecosystem |
| **E. pgvector** | Mature, transactional with the relational data | Requires Postgres |

## Decision

**B — Chroma**, strictly behind a `VectorIndex` interface with four methods:
`upsert`, `query`, `delete`, `count`.

## Reasoning

At the scale this system operates — thousands of strains, not millions — **every
option is fast enough**, so raw ANN performance is not the deciding factor.
Vector search is ~15 ms of a 300 ms budget in all five cases.

What actually decides it is operational simplicity and metadata filtering.
Metadata filtering is not optional here: entity-compatibility gating
([ADR-0008](0008-strain-identity.md)) needs to restrict candidates by
`claim_type` and organisation before scoring. FAISS would require building that
layer by hand.

Chroma also runs embedded with no separate process, which matters because the
system must run entirely on one laptop with the network disconnected
([ADR-0023](0023-cassette-replay.md)). C and E both add a service to start.

The interface is the real decision. Chroma's API has changed shape across minor
versions — a known operational hazard — and confining that surface to a single
adapter module means a breaking upgrade touches one file rather than the pipeline.

## Consequences

**Accepted costs:**
- Chroma API drift must be absorbed in the adapter, including trying
  `Settings(anonymized_telemetry=False)` and falling back to a bare
  `PersistentClient`.
- Not the fastest option; irrelevant at this scale, and revisited only if
  measurement says otherwise.

**Gained:**
- No extra process; runs offline.
- Metadata filtering available where the strain-identity gate needs it.
- One-file swap to Qdrant or pgvector when federation across institutions
  arrives ([Non-goals](../09-non-goals.md)).
