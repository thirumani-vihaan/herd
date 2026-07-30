# ADR-0008 — Strain identity requires semantic similarity AND entity compatibility

**Status:** Accepted

## Context

When is a new claim "the same rumour" as an existing strain? The obvious answer
is cosine similarity above a threshold. The obvious answer is dangerous here.

Consider two messages:

```
"Amazon off-campus drive for 2026 batch. Register at <link>. Fee ₹750."
"Deloitte off-campus drive for 2026 batch. Register at <link>. Fee ₹750."
```

Cosine similarity is very high — the template is identical and only a proper noun
differs. Under pure semantic matching these merge into one strain, and the second
message is served the first one's cached verdict.

That is a **correctness failure in both directions**. If the Amazon claim was
false and the Deloitte drive is real, HERD publicly labels a genuine placement
opportunity as fake — the single most damaging error the system can make
([Trust & safety](../06-trust-and-safety.md)). And if the Deloitte one is the
scam, it inherits an unrelated investigation's evidence, so the citations shown
to the user refer to the wrong company.

## Options

**A. Semantic similarity only.** Fast, and wrong as above.

**B. Entity match only.** Too brittle — misses genuine paraphrases and breaks on
extraction noise.

**C. Semantic similarity gated by entity compatibility.**

**D. Learn a similarity metric.** Requires labelled pairs the project does not
yet have. Deferred.

## Decision

**C.** A claim joins a strain only if **both** hold:

1. cosine similarity ≥ 0.88 (against either vector, [ADR-0006](0006-multilingual-embeddings.md)), **and**
2. entity compatibility passes.

Entity compatibility is asymmetric by entity type, because the types differ in how
much they change the claim's truth value:

| Entity type | Rule | Rationale |
|---|---|---|
| `organisations` | **Hard gate.** Different named org ⇒ different strain. | Changes what is being asserted entirely |
| `amounts` | Hard gate if both present and differ by > 20% | ₹750 vs ₹7500 is a different claim |
| `urls` (domain) | Hard gate on registrable domain | Different infrastructure, different investigation |
| `dates` | Soft — contributes to mutation scoring | Dates drift as a rumour is retold |
| `phones`, `upi_ids` | Soft, but a *match* strongly boosts confidence | Shared payment rail across "different" scams is highly diagnostic |
| `locations` | Soft | |

A hard-gate failure with high semantic similarity does not produce an unrelated
strain — it produces a **sibling** strain, linked to the same parent template.
That relationship is itself surfaced as evidence, and it is exactly the
"industrial template reuse" signal that
[`TemplateProvenance`](../03-investigation.md) exists to detect.

## Reasoning

The two signals fail in opposite directions, which is why combining them works:
embeddings are robust to rewording and blind to substitution; entity matching is
sensitive to substitution and brittle to rewording. The template-scam attack —
same message, swapped company — sits precisely in the blind spot of the first,
and is the dominant attack pattern in this domain.

Making `organisations` a hard gate while leaving `dates` soft reflects the actual
semantics: swapping the company changes what is claimed; a date drifting by a day
as the rumour is retold does not.

## Consequences

**Accepted costs:**
- Some genuine same-strain pairs are split when extraction misses an entity.
  Preferred direction — splitting causes a redundant investigation, merging causes
  a wrong public verdict.
- Cache hit rate is lower than pure semantic matching would report. The honest
  number is the lower one.
- Extraction quality now directly affects strain quality.

**Gained:**
- The most dangerous error class is structurally prevented rather than tuned away.
- Sibling linkage turns the hard gate into a *feature*: the "same poster, different
  company" pattern becomes evidence instead of a merge bug.
