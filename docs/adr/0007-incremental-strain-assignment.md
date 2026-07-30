# ADR-0007 — Incremental strain assignment, not batch clustering

**Status:** Accepted — supersedes the initial choice of HDBSCAN

## Context

Reports arrive one at a time, continuously, and each must be assigned to a strain
*immediately* — the user is waiting, and the sub-300 ms recognition budget is the
system's headline property.

The initial design specified HDBSCAN over claim embeddings. HDBSCAN is an
excellent density-based clustering algorithm, and it is the wrong tool here:
it is a **batch** algorithm. It partitions a fixed dataset and has no notion of
assigning a single new point. Running it per report is O(n log n) over the entire
corpus for every submission, and — worse — its cluster *labels are not stable
across runs*, so a strain's identity could change between two reports. Every
stored `strain_id`, every cached verdict, and every alert reference would be
invalidated by a re-run.

## Options

**A. HDBSCAN per report.** Correct clusters, unusable latency, unstable IDs.

**B. HDBSCAN periodically, nearest-centroid in between.** Two code paths and the
label-stability problem at every rebuild.

**C. Incremental threshold assignment.** Nearest existing strain centroid by
cosine; assign if above threshold, else create a new strain. O(log n) with an ANN
index, stable IDs by construction.

**D. Streaming clustering (BIRCH / online k-means).** Designed for streams, but
assumes a roughly known cluster count and struggles with the long tail of
singleton strains that dominate here.

## Decision

**C — incremental threshold assignment**, with a **periodic offline consolidation
pass** that merges over-fragmented strains without ever changing an existing ID.

Thresholds (validated empirically, not guessed —
[Evaluation](../07-evaluation.md)):

| Similarity to nearest centroid | Action |
|---|---|
| ≥ 0.88 | Same strain — attach, serve cached verdict |
| 0.72 – 0.88 | Mutation — create child strain, link to parent |
| < 0.72 | New strain — full investigation |

## Reasoning

The decisive property is **identity stability**. A `strain_id` is referenced by
cached verdicts, published alerts, the mutation tree, and any external link
someone has shared. It must be immutable. Batch clustering cannot promise that;
incremental assignment gives it for free.

The latency argument is equally decisive: nearest-centroid against an ANN index
is a few milliseconds, and it is the only option that fits the budget.

The consolidation pass handles the one genuine weakness of C — greedy assignment
can fragment a strain when early members are unrepresentative. Consolidation runs
off the hot path, and when it merges strains it does so by making one an **alias**
of the other rather than by renaming. Old IDs keep resolving forever.

This is a general lesson worth recording: the textbook-optimal algorithm for the
*offline* version of a problem is frequently wrong for its *online* version, and
the constraint that decides it is usually identity stability rather than accuracy.

## Consequences

**Accepted costs:**
- Assignment is greedy and order-dependent; a different arrival order could give
  a slightly different partition. Consolidation bounds the damage.
- Centroids drift as members accumulate — mitigated by a running mean and by
  storing the canonical claim separately from the centroid.
- Three thresholds now require empirical validation rather than being learned.

**Gained:**
- Millisecond assignment, meeting the recognition budget.
- Permanently stable strain IDs.
- Mutation detection falls out of the middle band naturally, rather than needing
  a separate mechanism.
