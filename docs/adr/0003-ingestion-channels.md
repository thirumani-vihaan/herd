# ADR-0003 — Ingestion channels

**Status:** Accepted

## Context

Given report-driven ingestion, through what channels do reports arrive? This
decision determines both adoption friction and demo reliability.

## Options

**A. WhatsApp Business Cloud API.** Where the problem actually lives — the
rumours circulate on WhatsApp, so accepting forwards there is the ideal path.

**B. Telegram bot.** Free, instant to provision, no verification, reliable API.

**C. Web app + QR code.** No install, works on every phone, paste/upload/drag.

**D. Native mobile app with a share-intent target.** Best long-term UX: "Share →
HERD" directly from WhatsApp.

## Decision

**C primary, B secondary, D as a thin Android share-target.** A is deferred.

## Reasoning

Option A is correct in principle and blocked in practice. WhatsApp Business Cloud
API requires Meta business verification — a multi-day-to-multi-week process
requiring a registered business entity. It cannot be relied on, and building the
primary path on a dependency that may not be approved is an unacceptable risk for
the one component that gates all input.

There is also a subtler problem with A: a WhatsApp Business number can only
receive messages sent *to it*, so users must still forward manually. The UX
advantage over Telegram is smaller than it first appears.

Option C wins as primary because it has **the lowest possible adoption cost**: a
QR code on a poster or a projector, scanned, and the user is submitting within
seconds with no install, no account, and no platform. It is also entirely
self-hosted, so nothing external can rate-limit or block the input path.

Option B complements it well: users who report via Telegram become *reliably
reachable* for interventions, which directly solves the delivery problem in
[ADR-0021](0021-intervention-channels.md). Telegram is thus not a second-class
input path but the primary *outbound* one.

Option D is a small amount of work for a real UX gain and no external dependency.

## Consequences

**Accepted costs:**
- Not present on the platform where the problem lives, so a manual forward step
  remains.
- Two inbound paths to maintain.

**Gained:**
- No external approval on the critical path; input cannot be blocked.
- QR distribution works on a poster, a slide, or a WhatsApp status.
- Telegram reporters are reachable, closing the intervention loop.

**Revisit when:** business verification completes, at which point WhatsApp
becomes an additional inbound channel feeding the same normalised `Report`.
