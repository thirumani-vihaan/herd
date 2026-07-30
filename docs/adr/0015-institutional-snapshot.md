# ADR-0015 — Pre-crawled institutional snapshot with RAG

**Status:** Accepted

## Context

The most useful question for a campus claim is "has the institution actually
announced this?" Answering it requires access to notices, circulars, and placement
pages.

## Options

**A. Live fetch on each investigation.** Always current. Fails when the site is
down or slow, and college websites are neither fast nor reliable.

**B. Pre-crawled snapshot, refreshed on a schedule, queried via RAG.**

**C. Official API / feed.** Does not exist for most institutions.

**D. Manual curation.** Accurate, unscalable.

## Decision

**B** — crawl on a schedule into a local vector index, query via RAG, with an
opportunistic live check for the single most relevant page when the network is
available and the snapshot is stale.

The crawl targets are not hardcoded. They come from the active institution
profile's `sources` block ([ADR-0026](0026-institution-profiles.md)), and the
resulting index is scoped by `institution_id` — one institution's notice board
is evidence about that institution and about nothing else.

## Reasoning

Three arguments converge.

**Latency.** Institutional sites frequently take seconds to respond. A local index
answers in milliseconds and keeps the investigation inside its budget.

**Availability.** The site being down must not degrade the investigation, and the
system must work with the network disconnected
([ADR-0023](0023-cassette-replay.md)). A snapshot satisfies both.

**Retrieval quality.** Notices are PDFs, images, and inconsistent HTML. Parsing
them well is genuinely slow work, and doing it once at crawl time rather than on
the hot path is straightforwardly better.

The important design detail is not the caching, though — it is the **asymmetry of
what absence means**. Finding an official notice that confirms the claim is
strong, near-conclusive support. *Not* finding one is weak evidence at best,
because colleges announce things late, inconsistently, over WhatsApp, or not at
all. The agent's contradicting strength is therefore capped while its supporting
strength is not.

Encoding that asymmetry matters more than the retrieval quality. A system that
treats "not on the notice board" as strong evidence of falsity would confidently
label genuine last-minute announcements as fake — precisely the error class that
[Trust & safety](../06-trust-and-safety.md) identifies as project-ending.

## Consequences

**Accepted costs:**
- Snapshot staleness between refreshes; mitigated by the opportunistic live check
  and by the low contradiction cap, which means staleness cannot cause a false
  accusation.
- A crawler to build and maintain per institution.
- Storage for the snapshot.

**Gained:**
- Millisecond retrieval, inside budget.
- Works offline.
- Robust to the institutional site being unavailable, which is common.
