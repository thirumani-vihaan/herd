# Institution profiles

Everything HERD knows about a specific institution lives here. Nothing
institution-specific belongs in code, prompts, or enums — see
[ADR-0026](../../docs/adr/0026-institution-profiles.md).

## The rule this directory exists to enforce

> A person who did not build HERD can stand up a new institution by writing one
> YAML file and running the crawler, in under an hour, touching no code.

If you find yourself editing a `.py` file to onboard a campus, the thing you are
editing belongs in this schema instead.

## Files

| File | What it is |
|---|---|
| `_template.yaml` | Commented blank. Copy this to start. |
| `vnrvjiet.yaml` | Reference tenant. Real institution, real public sources. |
| `demo-university.yaml` | **Synthetic.** Exists only to demonstrate cross-institution strain inheritance. Never presented as a real campus. |

Select the active profile with `HERD_INSTITUTION=<id>` in `.env`. The `id` must
equal the filename stem.

## What is global and what is scoped

This is the load-bearing distinction, so it is worth restating where the config
lives:

- **Scoped to the profile** — notice sources, official channels, cohort
  dimensions, calendar priors, and every `Evidence`, `Verdict`, `SpreadEstimate`
  and `Alert` derived from them.
- **Global, deliberately not in this directory** — strain identity and strain
  memory. A strain learned at one institution is recognised at every other one.

A strain sighted elsewhere contributes bounded prior odds to the local
investigation. It never carries a verdict across a boundary.

## Honesty markers

Profile authoring is research, and research is incomplete. Any field whose value
was assumed rather than confirmed against a public source must be marked:

```yaml
cohorts:
  verified: false   # values assumed; confirm against the academics page
```

Unverified fields are usable but are excluded from anything shown to a user as
fact, and the loader logs them at startup. Guessing quietly is the failure mode
this prevents.
