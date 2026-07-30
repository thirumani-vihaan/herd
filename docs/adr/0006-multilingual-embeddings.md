# ADR-0006 — Multilingual embeddings, not English MiniLM

**Status:** Accepted — supersedes the initial choice of `all-MiniLM-L6-v2`

## Context

Strain matching is the compounding engine of the whole system: report #1 costs a
full investigation, reports #2..#N cost a vector lookup. That only works if
semantically identical claims land near each other in embedding space.

The initial design specified `sentence-transformers/all-MiniLM-L6-v2` — fast,
tiny, local, and the default choice in most tutorials.

**It is the wrong model for this data.** `all-MiniLM-L6-v2` is trained on English.
The claims here are code-mixed Telugu / Hindi / English, frequently romanised.
Two paraphrases of the same rumour — one in English, one in romanised Telugu —
would land far apart, the strain would fragment into many singletons, cache hit
rate would collapse, and the central thesis of the system would silently fail
while every unit test still passed.

This is the most consequential error in the first design pass, because it degrades
gracefully into looking fine.

## Options

**A. `all-MiniLM-L6-v2`.** 384-dim, ~80 MB, ~5 ms. English only.

**B. `paraphrase-multilingual-MiniLM-L12-v2`.** 384-dim, ~470 MB, ~15 ms.
50+ languages including Telugu and Hindi. Distilled specifically for paraphrase
similarity — which is exactly the task.

**C. `multilingual-e5-small`.** 384-dim, ~470 MB. Strong multilingual retrieval
benchmarks; requires `query:` / `passage:` prefixes.

**D. `LaBSE`.** 768-dim, ~1.8 GB. Best-in-class cross-lingual *alignment* — built
so that translations land in the same place.

**E. Gemini embedding API.** Strong multilingual, no local model. Network
dependency, per-call cost, rate limits.

**F. Translate to English first, then embed with A.**

## Decision

**B — `paraphrase-multilingual-MiniLM-L12-v2`** as the primary index, with the
English rendering (`Claim.text_en`, already produced by extraction) embedded as a
**second vector** and both consulted at match time.

## Reasoning

B is chosen over D on operational grounds: LaBSE's cross-lingual alignment is
better, but 1.8 GB and 768 dimensions is a heavy cost for a gain that the dual-
vector scheme largely recovers. B is trained on the paraphrase objective, which
matches the actual task — "is this the same claim reworded" — more closely than a
retrieval objective (C).

E is rejected outright for a reason specific to this system: embedding is on the
**hot path for every single report**, including cache hits. Putting a network call
there would destroy the sub-300 ms recognition latency that is the system's
headline property, and would make the compounding-cost argument false, since
matching would then cost money per report.

F is rejected because translation is lossy on exactly the code-mixed input that
motivated the change, and it adds an LLM call to the hot path — reintroducing E's
problem.

The dual-vector design deserves note: extraction already produces `text_en` at no
extra cost, so indexing both the native-form and English-rendered embeddings costs
one extra local inference (~15 ms) and covers the hard case where a rumour crosses
languages as it spreads. Match = max similarity over both vectors.

## Consequences

**Accepted costs:**
- ~470 MB model download and ~500 MB RAM.
- ~15 ms per embedding instead of ~5 ms — irrelevant against a 300 ms budget.
- Two vectors per claim, roughly doubling index size. Negligible at this scale.

**Gained:**
- Strains hold together across Telugu / Hindi / English and across script choice.
- Still fully local: no network on the hot path, no per-report cost, works offline.

**Verification:** threshold selection and matching quality are measured against
the adversarial mutation set, not assumed ([Evaluation](../07-evaluation.md)).
Cross-lingual pairs are a required category in that set precisely because this is
where the superseded choice would have failed.
