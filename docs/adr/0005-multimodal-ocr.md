# ADR-0005 — Multimodal LLM for OCR and extraction in one pass

**Status:** Accepted

## Context

A screenshot must become a structured `Claim`. Classically this is two stages:
OCR to text, then NLP to structure.

## Options

**A. Tesseract → LLM.** Free, local, offline. Poor on Telugu, poor on stylised
poster text, and loses all layout.

**B. PaddleOCR → LLM.** Much better multilingual accuracy than Tesseract, still
local. Heavier dependency, still discards layout and non-text content.

**C. Google Cloud Vision → LLM.** Excellent OCR, returns bounding boxes. Paid,
and still a two-stage pipeline.

**D. Multimodal LLM, single pass.** Image in, structured `Claim` out.

## Decision

**D — single-pass multimodal extraction**, with **B available as a fallback** when
the multimodal API is unavailable.

## Reasoning

The two-stage pipeline throws away exactly the information that matters here.
A WhatsApp scam screenshot is not a document — it is a *composition*, and the
signal is distributed across:

- text in three scripts, often mixed within one sentence
- a logo, whose presence and placement is itself a claim of authenticity
- UI chrome that encodes forward markers and timestamps
- emoji used as structural markers (🔴 URGENT, ✅ verified)
- layout that separates the "poster" from the covering message

Serialising all of that to a flat string first and then asking a text model to
reconstruct intent is a lossy step that no downstream model can undo. A
multimodal model sees the composition and can report, for instance, that the
Amazon logo is low-resolution and misaligned — an observation that has no
representation in OCR output at all.

The code-mixing case is decisive. `"exam postpone ayindi ra, 3rd year valla ki
notice vachindi"` written in a mix of Telugu script and romanised Telugu defeats
sequential OCR-then-parse, because the OCR stage must commit to a script
segmentation before any semantic context is available.

## Consequences

**Accepted costs:**
- An external API sits on the critical path for new strains — mitigated by
  cassettes ([ADR-0023](0023-cassette-replay.md)) and by the Tier-0 rules being
  able to operate on partial extraction.
- Non-deterministic output, requiring strict schema validation and repair retries.
- Per-image cost — which is precisely why the recognise stage exists, so that the
  vast majority of reports never invoke it.
- **The input is attacker-controlled**, so prompt injection is a live threat. The
  extractor is confined to emitting a validated schema and can never influence the
  verdict label ([ADR-0013](0013-deterministic-verdict-aggregation.md)).

**Gained:**
- One network call instead of two stages.
- Layout, logo, and emoji signals preserved.
- Code-mixed South Indian group-chat text handled without a script-segmentation
  stage.
