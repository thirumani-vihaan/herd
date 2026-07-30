# ADR-0011 — Tiered investigation cascade, not a parallel broadcast

**Status:** Accepted — supersedes the initial always-parallel swarm

## Context

The initial design fanned out to all six investigation agents in parallel on every
new strain. Parallelism is appealing: total latency equals the slowest agent
rather than the sum, and it produces a striking visualisation.

It is still the wrong architecture, for three reasons.

1. **It spends LLM tokens on questions a rule engine can answer.** A message
   demanding a ₹750 fee for a job application is settled by one deterministic rule
   with near-conclusive strength. Invoking open-web research on it is waste.
2. **p95 latency becomes the slowest dependency's p95.** One rate-limited API
   drags every investigation, including the trivially decidable ones.
3. **Cost grows linearly with attack volume** — which directly contradicts the
   thesis the system exists to demonstrate, that wider spread makes an attack
   *cheaper* to neutralise.

## Options

**A. Full parallel broadcast.** Simple, uniform latency, maximally wasteful.

**B. Strict sequential.** Cheapest, but latency is the sum, and it serialises
independent calls for no benefit.

**C. Tiered cascade — parallel within a tier, sequential across tiers, early exit
when evidence is decisive.**

**D. Learned routing.** A model predicts which agents are worth running. Needs
training data that does not exist yet, and makes the system harder to explain.

## Decision

**C — tiered cascade with asymmetric early exit.**

| Tier | Agents | Cost | Exit threshold |
|---|---|---|---|
| 0 | FraudHeuristics, TemplateProvenance | free, ~30 ms | \|posterior\| > 0.90 |
| 1 | DomainForensics, URLSafety, ContactForensics | free-tier APIs, ~1–3 s | > 0.85 |
| 2 | InstitutionalSource, OfficialChannel | local index + 1–2 fetches, ~2–4 s | > 0.80 |
| 3 | OpenWebResearch | LLM, ~3–5 s | — |

## Reasoning

C keeps parallelism exactly where it pays — independent calls inside a tier — while
removing it where it only spends money. The ordering is by cost-to-diagnosticity
ratio, so the cheapest highly-diagnostic signals are consulted first.

The **asymmetric exit** is the subtle and important part. Exiting early toward
`FALSE` requires more accumulated strength than exiting toward `UNVERIFIED`,
because the two errors are not equally costly: a slow answer is recoverable, a
false public accusation is not
([Trust & safety](../06-trust-and-safety.md)). Symmetric thresholds would optimise
average latency at the expense of the one error class that can end the project.

A secondary benefit is that the cascade is **more legible than a broadcast**. Six
agents finishing simultaneously is visually impressive and explains nothing.
Tiers escalating, then visibly stopping early because the answer is already
settled, shows the reasoning — the system's judgement becomes watchable rather
than merely fast.

## Consequences

**Accepted costs:**
- Worst case (Tier 3 reached) is slower than a full broadcast.
- Four exit thresholds require empirical calibration
  ([Evaluation](../07-evaluation.md)).
- An early exit can miss evidence a later tier would have found — bounded by
  requiring high accumulated strength to exit, and by re-running low-confidence
  cached verdicts after a TTL.

**Gained:**
- Most new strains resolve without an LLM call.
- Marginal cost falls with volume, making the compounding thesis measurable
  rather than asserted.
- The investigation is explainable as a sequence of decisions.
