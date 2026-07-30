# ADR-0009 — Multi-signal mutation detection

**Status:** Accepted

## Context

Rumours mutate as they spread: the company changes, the amount changes, the poster
gets recoloured, a line gets translated. Detecting mutation is what turns a flat
list of strains into a mutation *tree* — and the tree is both the most informative
artifact for a user and the strongest evidence of industrial template reuse.

## Options

**A. Semantic drift only.** Cosine distance from the parent centroid. Noisy —
paraphrase and genuine mutation look identical.

**B. Entity diff only.** Precise but blind to rewording, and fully dependent on
extraction quality.

**C. Image pHash only.** Excellent for template reuse, useless for text-only claims.

**D. All three, with an explicit dominant signal.**

## Decision

**D.** A child strain is created when the parent match falls in the 0.72–0.88 band
([ADR-0007](0007-incremental-strain-assignment.md)) *or* when an entity hard gate
fires at high similarity ([ADR-0008](0008-strain-identity.md)). The `MutationDiff`
records all three distances and names the `dominant_signal`.

## Reasoning

Each signal covers the others' blind spots, and — more importantly — the
*combination pattern* is itself diagnostic in a way no single signal is:

| semantic | entity | pHash | Interpretation |
|---|---|---|---|
| near | changed | near | **Template scam.** Same artwork, swapped target. Near-conclusive. |
| far | same | near | Same poster, rewritten covering message. Normal spread. |
| near | same | far | Retyped/rescreenshotted. Same claim, different capture. |
| mid | changed | far | Genuinely different claim. Probably not a mutation at all. |

Row one is the money. It is the pattern that demonstrates an attacker running a
campaign rather than a one-off, and it is only visible because three independent
signals are tracked rather than one.

Recording `dominant_signal` on every edge matters for a second reason: it is what
the mutation-tree UI shows on hover, so the user can see *why* two things were
linked. An unexplained edge in a graph is not evidence, it is decoration.

## Consequences

**Accepted costs:**
- Three computations per report instead of one. All are cheap and local.
- pHash requires size normalisation before hashing or the signal is noise.
- Text-only reports have no pHash channel; the diff records this rather than
  imputing a value.

**Gained:**
- Template reuse becomes detectable and citable evidence.
- Mutation edges are explainable, so the tree is legible rather than decorative.
