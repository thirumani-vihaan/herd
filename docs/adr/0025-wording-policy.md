# ADR-0025 — Evidence-only wording, never accusation

**Status:** Accepted

## Context

Every user-facing string HERD produces is a public statement about someone else's
message, and often about a named organisation. The difference between a useful
public-interest tool and a defamation problem is substantially a matter of
wording.

## Options

**A. Plain language.** "This is a scam." Maximally clear, maximally exposed.

**B. Heavy hedging.** "It is possible that this may potentially be unverified."
Safe, and so weak that nobody acts on it — which defeats the purpose.

**C. Evidence-forward.** State the checkable facts and their sources; let the
label carry the conclusion; never editorialise about intent or character.

## Decision

**C.**

| Never | Always |
|---|---|
| "This is a scam" | "We could not verify this, and these signals are concerning" |
| "X is a fraudster" | "The domain in this message was registered on 26 July 2026" |
| "Fake" as a bare label | `FALSE` with its evidence one tap away |
| Any claim about intent | Only claims about artifacts |

Enforced mechanically: a post-generation check rejects any sentence containing an
entity not present in the evidence set, and the prose model is constrained to
writing over evidence rather than adding to it
([ADR-0013](0013-deterministic-verdict-aggregation.md)).

## Reasoning

Option B is the instinctive safe answer and is genuinely worse than A. A warning
so hedged that nobody changes their behaviour has all of the cost of being wrong
and none of the benefit of being right. Safety that comes from being ignored is
not safety.

C resolves the tension because **the facts are usually more persuasive than the
accusation anyway.** "This domain was registered four days ago and Amazon's
careers page lists no such drive" is more convincing to a sceptical reader than
"this is a scam", *and* it is a statement of verifiable fact rather than an
allegation about a person. The safer formulation is also the more effective one.

Restricting statements to **artifacts rather than people** is the load-bearing
rule. HERD describes domains, payment methods, templates, and pages. It never
describes who is behind them. Attribution is law enforcement's job and requires
powers and accountability this system does not have
([Non-goals](../09-non-goals.md)).

The mandatory `what_would_change_my_mind` field belongs to this decision too: a
verdict that publishes its own falsifier is a claim being made in good faith and
open to correction, which is a materially different posture — legally and
ethically — from an unqualified assertion.

## Consequences

**Accepted costs:**
- Slightly longer messages than a bare "SCAM" label.
- Users must read one more line to reach the conclusion. Mitigated by the label
  carrying it and the evidence supporting it.
- The prose model is constrained, so output is less fluent than free generation.

**Gained:**
- Statements are factual and sourced, which is both defensible and more
  persuasive.
- No claims about intent or character anywhere in the system.
- A concrete, checkable basis for appeals rather than a negotiation.
