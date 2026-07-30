# ADR-0017a — LangGraph for investigation orchestration

**Status:** Accepted

## Context

The cascade ([ADR-0011](0011-tiered-investigation-cascade.md)) has tiers that run
in sequence, agents that run in parallel within a tier, conditional early exit,
per-agent timeouts, and a live event stream that the UI renders. Something must
express that control flow.

## Options

**A. Plain `asyncio`.** `asyncio.gather` per tier, `if` between tiers. No
dependency, complete control, and the control flow lives in imperative code.

**B. LangGraph.** Explicit graph of nodes and edges, built-in state management,
streaming, and conditional edges.

**C. CrewAI.** Higher-level agent abstractions, opinionated toward autonomous
role-playing agents.

**D. AutoGen.** Conversation-centric multi-agent framework.

## Decision

**B — LangGraph**, with the cascade expressed as tier nodes and conditional edges.

## Reasoning

C and D are rejected quickly: both are built around agents that *converse* to
reach consensus, which is precisely the design rejected in
[ADR-0012](0012-evidence-not-verdicts.md). Their core abstraction fights this
architecture rather than supporting it.

A is genuinely competitive and would work. It is rejected on two grounds:

**Streaming.** The UI's investigation trace is the system's most important visual
([UI doctrine]), and it needs a structured event per node start, node finish, and
tier transition. LangGraph emits this natively. With plain asyncio it would be
hand-rolled event plumbing threaded through every call site — the kind of
cross-cutting concern that ends up inconsistent.

**Legibility.** The graph is declared in one place, so the control flow is
inspectable as data rather than inferred by reading imperative code. For a system
whose selling point is that its reasoning is watchable, having the reasoning
structure be a first-class object is worth a dependency.

**The critical constraint:** LangGraph nodes must return **update dictionaries
only** and must never mutate the input state in place. In-place mutation appears
to work, then fails in ways that are invisible — no exception, just state that
silently does not propagate. This is enforced by a smoke test that fails the
build if a node mutates its input.

## Consequences

**Accepted costs:**
- A dependency with its own version churn.
- The update-dict discipline must be enforced by test, not by convention.
- Debugging goes through a framework's abstractions rather than a stack trace.

**Gained:**
- Streaming events for the trace UI without hand-rolled plumbing.
- Control flow declared as inspectable data.
- Adding a tier or an agent is a graph edit, not a control-flow rewrite.
