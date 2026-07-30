# ADR-0022 — Single process with SQLite for v1

**Status:** Accepted — supersedes Redis Streams + Postgres

## Context

The initial design specified Redis Streams for the task queue and a separate
database service. That is a reasonable production architecture and the wrong
choice for this system's actual requirements.

## Options

**A. Redis + Postgres + separate worker processes.** Scales horizontally, standard
production shape, and requires three services running correctly and simultaneously.

**B. Single process, SQLite, in-process async task queue.**

**C. Serverless / managed services.** Adds a network dependency to the hot path,
which contradicts the offline requirement.

## Decision

**B**, with `TaskQueue`, `Store`, and `VectorIndex` as abstract interfaces so the
migration to A is a configuration change rather than a rewrite.

## Reasoning

Distributed infrastructure buys throughput this system does not need and costs
reliability it cannot afford.

**Throughput.** One campus generates reports at a rate a single process handles
with enormous headroom. Redis Streams solves a problem that does not exist here.

**Reliability.** Every additional service is another thing that can fail to start
at the wrong moment. The requirement that the system run with the network
disconnected on unfamiliar hardware makes "three services must be up" a real
liability rather than a theoretical one. **Fewer moving parts is a feature, not a
compromise.**

**Honesty.** Building for a scale the system has not reached is the most common
form of engineering theatre. A system that runs correctly on a laptop and has
clean seams for scaling is a better artifact than one that requires a compose file
to demonstrate anything.

SQLite specifically: with **WAL mode** it handles concurrent readers with a single
writer comfortably, which matches the access pattern exactly — many dashboard
reads, one ingestion writer.

The interfaces are the part that makes this defensible rather than lazy. Because
`TaskQueue`, `Store`, and `VectorIndex` are ABCs with the real implementation
constructed in one named place, moving to Redis and Postgres for a multi-campus
deployment is a new adapter plus a config flag.

## Consequences

**Accepted costs:**
- No horizontal scaling until the interfaces are reimplemented. Accepted; that is
  a real milestone, not a v1 requirement.
- Long-running investigations share a process with the API. Mitigated by them
  being async and I/O-bound, plus a bounded worker pool.
- SQLite write contention under heavy concurrent ingestion. WAL mode and a single
  writer make this comfortably sufficient at this scale.

**Gained:**
- One process to start. Runs anywhere, offline, with no orchestration.
- No `database is locked` class of failure from misconfigured concurrency.
- Dramatically fewer failure modes at the moment when failure is least affordable.
