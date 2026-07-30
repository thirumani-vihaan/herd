# ADR-0013 — Deterministic aggregation sets the label; the LLM writes the prose

**Status:** Accepted — supersedes the initial LLM-synthesiser design

## Context

The initial design had a "Synthesiser" node: feed all evidence to an LLM, receive
a `Verdict` with label, confidence, and reasoning. It is the obvious design and it
is used widely.

It puts a non-deterministic, attacker-influenceable component in charge of the one
field that can defame someone.

## Options

**A. LLM produces the verdict.** Flexible, handles nuance, one call.

**B. Rules produce the verdict.** Deterministic, auditable, brittle on nuance.

**C. Rules produce label and confidence; LLM writes the human-readable prose.**

**D. LLM proposes, rules veto.** Still lets the LLM set the label in the common
case, so it inherits A's problems.

## Decision

**C.** Evidence is combined in log-odds space with per-agent reliability weights
and correlation-group discounting. The posterior maps to a label through
calibrated bands. **Only then** is an LLM asked to write `headline`, `reasoning`,
and `what_would_change_my_mind` — constrained to the evidence already gathered,
introducing no new facts.

A post-generation check verifies every entity in the prose appears in the evidence
set. Failure triggers a retry, then a deterministic template.

## Reasoning

Three arguments, each sufficient on its own.

**1. Security.** The input is a screenshot supplied by an adversary. Prompt
injection is not hypothetical — a poster can contain text addressed to the model.
If the LLM sets the label, an attacker who lands an injection controls the
verdict. Under C, the injected text can at most influence *extraction*, whose
output is schema-validated and cannot reach the label. **This makes the decision a
security control, not a stylistic preference.**

**2. Calibration.** LLM-stated confidence is not calibrated and does not become
calibrated with prompting. A log-odds aggregator with learned weights can be
measured against ground truth and corrected ([Evaluation](../07-evaluation.md)).
A number users act on must mean something.

**3. Auditability and reproducibility.** "Why did this get labelled FALSE?" must
have an answer that is a list of weighted evidence, not a model's inference. Two
runs on identical evidence must produce an identical label — otherwise the appeals
process in [Trust & safety](../06-trust-and-safety.md) is meaningless.

The correlation-group discounting deserves emphasis. Naive log-odds addition
assumes independence, which is plainly false: "URL shortener", "young domain", and
"free-mail sender" co-occur because they come from the same attack kit. Summing
them independently over-counts and drives the posterior to certainty on weak
evidence. Within a correlation group, only the strongest signal contributes at
full weight. **This one detail is the difference between a calibrated system and
one that always outputs 0.99.**

## Consequences

**Accepted costs:**
- Genuinely novel evidence patterns the rules do not encode are handled less
  gracefully than an LLM would handle them. Those cases land in `UNVERIFIED`,
  which is the correct behaviour for a system that does not understand something.
- Weights and correlation groups must be maintained and periodically recalibrated.
- Two stages instead of one.

**Gained:**
- Prompt injection cannot change a verdict.
- Confidence numbers mean what they say.
- Verdicts are reproducible and explainable, so they can be appealed.
