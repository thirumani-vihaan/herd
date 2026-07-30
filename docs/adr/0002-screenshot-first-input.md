# ADR-0002 — Screenshot-first input

**Status:** Accepted

## Context

A user wants to submit a suspicious message. What is the primary input modality?

## Options

**A. Text-first.** User pastes the message text. Simple, cheap, no OCR.

**B. Screenshot-first.** User uploads or pastes an image; the system reads it.

**C. Link/URL-first.** User submits the suspicious link only.

## Decision

**B — screenshot-first**, with text as a fully supported secondary path.

## Reasoning

This is a decision about observed behaviour rather than engineering convenience.
Messages of this kind travel as **images**: a poster with a company logo, or a
screenshot of a forwarded message. When someone asks a friend "is this real?",
they send a screenshot. Text-first would ask users to do the awkward extra work
of extracting text from an image, which is the point at which most people give up.

Screenshots also carry information the text does not:

- **Forward markers** — WhatsApp's "forwarded many times" indicator is a direct
  spread signal, and it is the closest thing to network data that a non-monitoring
  system can obtain.
- **Original message timestamp** in the UI chrome, which materially reduces
  observation lag ([ADR-0018](0018-report-process-bias.md)).
- **Visual template**, enabling perceptual-hash matching that catches the same
  scam poster recoloured for a different company — the most diagnostic signal in
  the entire system ([ADR-0009](0009-mutation-detection.md)).

Option C is too narrow: a large fraction of these messages contain no link at all
("exams postponed", "fee deadline extended").

## Consequences

**Accepted costs:**
- OCR is now on the critical path, with all its failure modes on code-mixed text.
- Images are heavier to transport and store.
- A screenshot is a photograph of other people's data, which forces the redaction
  requirement in [Trust & safety](../06-trust-and-safety.md).

**Gained:**
- Matches the behaviour that already exists; zero friction.
- Three signal channels the text path cannot provide.
- Template provenance, which is the strongest evidence HERD produces.
