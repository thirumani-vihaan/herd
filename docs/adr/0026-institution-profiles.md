# ADR-0026 — Institution as a loaded profile; strain memory global, evidence scoped

**Status:** Accepted
**Supersedes:** the implicit single-institution assumption in
[ADR-0015](0015-institutional-snapshot.md) and the "deferred" listing of
multi-institution federation in [Non-goals](../09-non-goals.md).

## Context

HERD was first sketched against one college. That is the wrong shape, and not
only for commercial reasons — it is wrong about **which parts of the system
actually generalise**.

Sorting the evidence sources by what they depend on makes the split obvious:

| Signal | Depends on the institution? |
|---|---|
| URL reputation, domain age (RDAP), redirect chain | No |
| Payment-rail heuristics (fee-to-apply, UPI handle shape) | No |
| Linguistic manipulation analysis | No |
| **Strain memory — "we have seen this pattern before"** | **No** |
| Official-notice retrieval | Yes |
| Official-channel identity ("is this the real placement cell handle?") | Yes |
| Cohort taxonomy for targeting (year, branch, hostel, programme) | Yes |
| Academic calendar priors (fee windows, exam weeks, drive season) | Yes |

Four of the eight signals are institution-independent, and the single most
valuable one — strain memory — is among them. A scam template that extracted
₹750 from students at one campus is *the same template* when it arrives at the
next campus a week later, usually with only the college name swapped.

This produces the central tension. The asset gets **more** accurate the more
widely it is shared, while institutional evidence becomes **actively wrong** when
shared: "this is not on the notice board" is meaningful about the campus that
owns that notice board and meaningless about every other campus. A naive
"just make it multi-tenant" that shares everything would manufacture false
verdicts; a naive "keep everything separate" would throw away the only network
effect the system has.

## Options

**A. Hardcode one institution.** Fastest to build. Every institutional detail
leaks into agent code, prompts, and the cohort enum. Adding a second campus is a
rewrite, and the system cannot answer the first question any evaluator asks.

**B. Institution as a config profile; one active profile per process; strain
memory in a global namespace.**

**C. Full runtime multi-tenancy** — tenant resolved per request, row-level
isolation, per-tenant auth and quotas.

**D. Federation** — independent per-campus deployments that gossip strain
records to each other.

## Decision

**B**, with `institution_id` present as a first-class field on every
tenant-scoped record from the first migration, and strain identity deliberately
placed **outside** that scope.

Concretely:

1. An institution is a YAML profile in `config/institutions/<id>.yaml`. Nothing
   institution-specific appears in code, prompts, or enums.
2. The process loads exactly one profile at boot (`HERD_INSTITUTION`). There is
   no per-request tenant resolution in v1.
3. `institution_id` is on `Report`, `Evidence`, `Verdict`, `SpreadEstimate`,
   `Alert`, and `Cohort` from day one — even though v1 only ever writes one
   value into it.
4. `Strain` has **no** `institution_id`. It carries
   `seen_at: list[InstitutionSighting]` instead.
5. A strain seen elsewhere enters the aggregator as one bounded `StrainPrior`
   signal    ([ADR-0013](0013-deterministic-verdict-aggregation.md)) — never as a verdict.

## Reasoning

**Why not A.** Beyond the obvious, hardcoding gets the epistemics wrong. It
encourages treating "the notice board is silent" as a general fact rather than a
fact about one institution, which is exactly the reasoning error
[Trust & safety](../06-trust-and-safety.md) identifies as project-ending.

**Why not C or D in v1.** Request-scoped tenancy costs auth, isolation tests,
per-tenant quotas, and a whole class of leak bugs, in exchange for a capability
nothing exercises yet. [ADR-0022](0022-single-process-v1.md) already argues that
fewer moving parts is a reliability feature. Federation (D) additionally needs a
trust model between deployments — how do you know the peer's strain records are
honest? — which is a genuinely hard problem and not one worth solving before
there is a second deployment.

**Why the schema key goes in now anyway.** This is the asymmetry that decides the
ADR. Deferring the *runtime* is cheap and reversible. Deferring the *key* is
neither: retrofitting a tenant column into a populated schema means touching
every query, every index, and every aggregate, under the constraint that missing
one produces silent cross-tenant leakage rather than an error. Pay the cheap part
now, defer the expensive part.

**Why strain memory is global.** Making it global costs nothing — it is the
absence of a filter — and it is the entire growth argument. Campus #2 does not
start from zero; it inherits every strain campus #1 has already paid to learn.
That inverts the usual cold-start problem: the system is *most* valuable to the
newest adopter, because they get the accumulated immunity for free.

**Why a bounded prior rather than a shared verdict.** Global strain memory has
one real failure mode: a wrong or poisoned conclusion at one institution
propagating everywhere. The containment is to share the *pattern* and re-derive
the *conclusion*:

> Strain identity is global. Verdicts are always re-derived per institution from
> that institution's own evidence. A prior sighting contributes bounded prior
> odds and can never, alone, reach a verdict threshold.

So a strain confirmed fraudulent at three other campuses arrives here as a strong
hint that shortens the investigation — the cascade escalates faster — but the
label still has to be earned locally. This preserves the cost story (recognition
is cheap) without importing another institution's mistakes.

The entity hard gates from [ADR-0008](0008-strain-identity.md) do useful double
duty here: because differing `organisations` already force distinct strains,
a swapped college name in an otherwise identical message is correctly treated as
the *same* strain only when the organisation being impersonated is the same.

**Why the cohort taxonomy has to move into the profile.** `year ∈ {1,2,3,4} ×
branch ∈ {CSE, ECE, EEE, MECH, CIVIL}` is not a domain model, it is one
institution's org chart. Elsewhere the meaningful cohort axis is programme,
hostel block, department, or campus. Targeting
([Intervention](../05-intervention.md)) therefore reads cohort *dimensions* from
the profile and treats them opaquely.

## The falsifiable test

"Institution-agnostic" is an easy claim to assert and a hard one to earn, so it
gets an acceptance criterion rather than an adjective:

> A person who did not build HERD can stand up a new institution by writing one
> YAML file and running the crawler, in under an hour, touching no code. The
> full demo must then pass against that profile.

If any step of that requires editing a `.py` file, this ADR is not implemented.

## Consequences

**Accepted costs:**
- A profile schema to design, validate, and document — and the discipline to
  keep institutional facts out of prompts, where they tend to accumulate.
- One indirection between agents and the values they use.
- `institution_id` on records that v1 never varies, which will look like
  over-engineering to a reader who has not read this ADR.
- The cross-institution path is real but lightly exercised in v1; it is proven by
  a clearly-labelled synthetic second profile, not by a second live deployment.

**Gained:**
- The growth answer is a demonstrated behaviour rather than a slide: a strain
  learned at one institution is recognised instantly at another.
- No rewrite between one campus and many — C becomes routing, D becomes a
  transport, and neither is a migration.
- Institutional reasoning stays honest, because the scoping is enforced by the
  schema rather than by remembering.
