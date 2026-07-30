# ADR-0023 — Cassette-based replay mode

**Status:** Accepted

## Context

The system depends on several external services: an LLM API, RDAP, Safe Browsing,
and remote page fetches. Each can be slow, rate-limited, or unreachable. The
system must nonetheless be fully demonstrable and fully testable without any of
them.

## Options

**A. Mocks in tests only.** Standard, and leaves the running application dependent
on live services.

**B. A `--offline` flag with hardcoded canned responses.** Works, but the responses
drift from reality and the flag path is not the real code path.

**C. Cassette record/replay.** Real responses recorded on a live run, replayed
byte-for-byte with original latencies preserved.

## Decision

**C.** `DEMO_MODE=replay` routes every `HttpFetcher` and `LLMClient` call through
`app/cassette.py`.

## Reasoning

The essential property is that **replay exercises the real code path.** Under B,
the offline mode is a different branch, so passing offline proves nothing about
the live system — and worse, the offline branch rots silently because nothing
tests it against reality.

Under C the client, the parsing, the error handling, the retry logic, and the
aggregation are all identical; only the transport is swapped. A bug in response
parsing surfaces in replay exactly as it would live.

**Preserving original latencies** is not cosmetic. If replay returned instantly,
every timing-dependent behaviour would be untested: the tier timeouts, the
parallel-within-tier concurrency, the progressive rendering of the trace UI. A
system that only works when its dependencies are infinitely fast is not tested.
Preserved timings also mean the visual pacing of a demonstration is identical
online and offline.

Cassettes double as **regression fixtures**. A recorded response is a real,
messy, honest sample — including whatever malformed edge case production actually
returned — which is a far better test input than a hand-written ideal response.

This is therefore a correctness feature that happens to also be a demo feature.
Integration tests run against cassettes in CI, which is what makes the suite
runnable offline by anyone with no credentials.

## Consequences

**Accepted costs:**
- Cassettes go stale as APIs change. Mitigated by re-recording on a schedule and
  by a test that diffs a live response against its cassette when credentials are
  present.
- Recorded responses may contain sensitive content, so cassettes are scrubbed of
  credential-shaped strings before being written.
- Storage for recorded fixtures.

**Gained:**
- Full functionality with the network disconnected, through the real code path.
- Deterministic, fast, credential-free tests.
- Realistic fixtures obtained for free rather than invented.
- Identical demonstration pacing online and offline.

**Interaction with [L3 / no fabricated data]:** replay is *recorded reality*, not
invented data, which is why it is permitted. It is nonetheless labelled — the API
sets `X-HERD-Mode: replay` and the UI shows a chip — because presenting recorded
data as live would be exactly the dishonesty the rule exists to prevent.
