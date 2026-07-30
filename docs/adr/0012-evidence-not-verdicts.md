# ADR-0012 — Agents return evidence, never verdicts

**Status:** Accepted

## Context

Each investigation agent learns something about a claim. What shape does it
return?

## Options

**A. Each agent returns a verdict**, and the system takes a majority or weighted
vote. This is the common multi-agent pattern.

**B. Each agent returns a confidence score** on falsity.

**C. Each agent returns evidence** — a factual finding, a direction, a strength,
and citations — and a separate stage decides.

## Decision

**C.** An agent may report "the company's careers page lists no such drive". It
may not report "this is fake".

## Reasoning

Option A degrades into six language models voting on an impression. Their errors
are correlated — they share training data and reasoning failure modes — so
agreement between them is much weaker evidence than it appears, and the vote
manufactures false confidence.

The decisive argument is **auditability**. A user who is told "4 of 6 agents said
fake" has learned nothing and cannot check anything. A user shown "Amazon's
careers page, retrieved 14 minutes ago, lists no such drive" and "this domain was
registered on 26 July" can verify both claims independently. The system's
authority comes from the citations, not from its own assertion — which is the only
form of authority it is entitled to.

There is also a security consequence. The input to this system is
attacker-controlled text, and an attacker who can make one agent output a verdict
can move the outcome. When agents can only contribute *cited findings*, and
citations are checked against retrieved sources, that attack surface largely
closes ([ADR-0013](0013-deterministic-verdict-aggregation.md)).

Separating `signal` (direction) from `strength` (diagnosticity) is what makes
principled aggregation possible at all. "Domain is 4 days old" is a weak
contradicting signal; "the official careers page lists no such drive" is a strong
one. Collapsing both into a single confidence number destroys the information the
aggregator needs.

## Consequences

**Accepted costs:**
- A separate aggregation stage must exist and be correct.
- Agents cannot short-circuit on their own; the cascade controller decides.
- More structure to define and validate than "return a string".

**Gained:**
- Every verdict is backed by checkable citations.
- Agent reliability can be measured per agent and fed back as weights.
- Adding an agent cannot destabilise existing behaviour — it adds evidence to a
  calibrated aggregator rather than a vote to a poll.
