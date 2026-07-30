# ADR-0024 — Explicit scope guard, with refusal as a first-class outcome

**Status:** Accepted

## Context

Users will submit anything. Some claims are outside what this system can
responsibly adjudicate, and attempting them causes harm that no amount of accuracy
compensates for.

## Options

**A. Attempt everything.** Maximum coverage, unbounded liability.

**B. Refuse silently** — return `UNVERIFIED` for out-of-scope claims without
explanation. Looks like incompetence rather than judgement.

**C. Explicit scope guard** with `OUT_OF_SCOPE` as a designed, explained outcome.

## Decision

**C.** A classifier runs immediately after extraction. Out-of-scope claims are
refused with a stated reason and, where appropriate, a pointer to a better source.

| Refused category | Reason |
|---|---|
| Political / electoral | No stable ground truth; verdicts become partisan artifacts and the tool is immediately weaponised |
| Religious / communal | Same, with worse consequences in this context |
| Medical advice | Requires clinical authority the system does not have |
| Claims about named private individuals | Defamation surface with no offsetting public interest |
| Opinions, predictions, satire | Not falsifiable |

In scope: `job_drive`, `exam_schedule`, `fee_deadline`, `event`, `scholarship`,
`government_scheme`, `safety_alert`, `lost_and_found`.

## Reasoning

**Narrowness is what makes trustworthiness achievable.** A tool that adjudicates
institutional claims can be evaluated, calibrated, and verified against ground
truth. A tool that adjudicates everything cannot be evaluated at all, and is
therefore trusted for nothing.

Each refusal is specific rather than squeamish:

- *Political claims* have no ground truth the system can cite. Any verdict becomes
  a political act, and the tool's first controversial call would end its
  usefulness for the boring institutional claims where it is genuinely valuable.
- *Named individuals* is the sharpest line. The public interest in "is this
  placement drive real" is clear; there is none in adjudicating an accusation
  about a person, and the harm from being wrong is severe and personal.
- *Medical* is a competence boundary. Being wrong there hurts people in ways a
  wrong verdict about a fest venue does not.

The guard is run **after extraction but before investigation**, so refusal costs
nothing and out-of-scope content is never sent to investigation agents or stored
as a strain.

Making refusal *explicit and explained* rather than silent is what turns a
limitation into a demonstration of judgement. "We don't adjudicate claims about
individuals" reads as principle; a bare `UNVERIFIED` reads as failure.

## Consequences

**Accepted costs:**
- Real misinformation in refused categories goes unaddressed. Accepted knowingly;
  it is not this system's job.
- The classifier can mis-route, so borderline cases default to **refusing**, and
  users can flag a wrongly-refused claim for review.
- Coverage looks narrower than a maximalist competitor's.

**Gained:**
- A bounded, evaluable problem, which is what makes the precision targets in
  [Evaluation](../07-evaluation.md) meaningful.
- The tool cannot be weaponised for political or personal disputes.
- Refusal demonstrates judgement rather than incapacity.
