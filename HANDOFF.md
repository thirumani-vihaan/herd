# HANDOFF

State of HERD as of the last commit on `main`. Written for whoever (human or
agent) picks this up next. Read this file first, then `SPEC_DIGEST.md`.

---

## 1. What HERD is

An **immune system for campus misinformation**. A student forwards a suspicious
WhatsApp screenshot; HERD extracts the claim, recognises whether it has seen
that *template* before, investigates it with a tiered cascade of cheap-to-
expensive agents, produces a cited verdict, models how far the message is
spreading, and warns the cohorts that have not been reached yet.

The three things that make it different from "an LLM that says fake or real":

1. **The label is arithmetic, never the model's opinion.** An LLM writes prose
   *after* the label is fixed (ADR-0013). Every number is traceable.
2. **It recognises strains, not messages.** The same scam mutates constantly;
   HERD tracks the operation across mutations and across institutions, so the
   second campus to see it gets an answer in milliseconds.
3. **It refuses to be confidently wrong.** Abstention is a first-class outcome.
   Several design decisions exist purely to make a false accusation harder.

---

## 2. Ground rules that must not be broken

These are not style preferences. Each one was earned by a bug.

| Rule | Why |
|---|---|
| `app/contracts.py` and `app/interfaces.py` are **FROZEN**. When code and contract disagree, the **contract is right**. | It has been right every single time so far. |
| **No numeric literal in `app/`** — every tunable lives in `config/thresholds.yaml`. Enforced by AST tests. | A second copy of a calibrated number silently wins after recalibration. |
| **No institutional string in `app/` or `web/`.** Institution facts arrive only via `app/institution.py` → the injected `Institution` object. | The portability claim: switch `HERD_INSTITUTION`, change nothing else. |
| **No agent may raise.** Failure ⇒ `status="unavailable"`, `strength=0`. | Enforced twice: inside each agent, and again by `Cascade._run_one` from the outside. |
| **Every non-neutral finding cites ≥1 `Source`.** | Schema-enforced by a validator on `Evidence`. |
| **Push after every feature** via `pwsh -NoProfile -File tools\push.ps1 -Message $msg`. | It secret-scans, pushes with the token inline, and re-verifies `.git/config`. |
| **No Copilot / AI co-author trailers in commits, ever.** | History was purged once already; do not reintroduce. |
| Re-run `tools/calibrate_aggregation.py` (and `tools/calibrate_thresholds.py`) after **any** change to fraud rules or extraction. | Extraction changes shift entities, which shift every downstream number. |

---

## 3. Environment

- Python **3.11.9** at `venv\Scripts\python.exe`. **Always invoke by full path.**
  Bare `python` is the system interpreter with none of the dependencies.
- Every `powershell` tool call is a **fresh process** — no cwd or env persistence.
- PowerShell has no heredocs. To run an inline script:
  `@'` … `'@ | & "$h\venv\Scripts\python.exe" -` (piped to **stdin**).
- The `create` tool cannot overwrite. `Remove-Item` first, or use `edit`.
- f-strings cannot contain backslashes on 3.11 — assign to a variable first.
- Non-ASCII in PowerShell output gets mangled (`±` → `?`). Harmless.

`.env` (gitignored) holds `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-2.0-flash`,
`GOOGLE_SAFE_BROWSING_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`HERD_INSTITUTION=vnrvjiet`, `DEMO_MODE=live`.

**Git push:** there is no `gh` CLI. The only PAT lives in another repo's remote:

```powershell
$url = git -C "$env:USERPROFILE\Desktop\tutor\MentorOverlay" config --get remote.personal.url
```

`tools\push.ps1` already does this. Use it; do not hand-roll a push.

---

## 4. What exists and works today

**168 tests green.** Everything below is committed and pushed to
`github.com/thirumani-vihaan/hackathon`.

### Layers complete

| Layer | Files | Status |
|---|---|---|
| Contracts & interfaces | `app/contracts.py`, `app/interfaces.py` | Frozen, complete |
| Config | `app/config.py`, `config/thresholds.yaml`, `config/fraud_rules.yaml`, `config/institutions/*.yaml` | Complete |
| Institution profiles | `app/institution.py` | Complete |
| Perceive | `app/perceive/redact.py`, `app/perceive/extract.py` | Complete |
| Recognise | `app/recognise/strain.py` | Complete |
| Storage | `app/storage/sqlite_store.py` | Complete |
| Aggregation | `app/investigate/aggregate.py` | Complete, calibrated |
| Cascade | `app/investigate/cascade.py` | Complete |
| Tier 0 agents | `app/investigate/agents/tier0.py`, `memory.py` | Complete |
| Tier 1 agents | `app/investigate/agents/tier1.py` | Complete |
| HTTP port | `app/clients/http.py` | Complete |
| Test doubles | `tests/fakes.py` | Complete |
| Fixtures | `fixtures/` — 35 labelled synthetic screenshots | Complete but **see §6** |

### The nine agents

| Tier | Agent | What it does | Network? |
|---|---|---|---|
| 0 | `FraudHeuristics` | 10 structural rules over claim text, netted both directions | no |
| 0 | `TemplateProvenance` | WhatsApp forwarding chrome (ADR-0018) | no |
| 0 | `StrainPrior` | Reuses HERD's own past verdict on this strain | no |
| 1 | `DomainForensics` | Impersonation / lookalike / cheap TLD (offline) + RDAP domain age (online) | half |
| 1 | `URLSafety` | Google Safe Browsing v4 | yes |
| 1 | `ContactForensics` | Mail domain, freemail, phone, UPI handle vs verified profile | no |
| 2 | `InstitutionalSource` | **NOT BUILT** — snapshot RAG over the college's own site | — |
| 2 | `OfficialChannel` | **NOT BUILT** — careers page / official channels | — |
| 3 | `OpenWebResearch` | **NOT BUILT** — LLM open-web research, terminal tier | — |

### Measured results (offline, network blocked)

```
venv\Scripts\python.exe tools\eval_tier0.py --with-tier1
```

- 13/13 scams detected (11 FALSE, 1 MISLEADING, 1 UNVERIFIED)
- **0/14 genuine notices accused**
- **0 confirmed TRUE without a source**
- worst-case margin to an error: **0.214 posterior units**
- sub-millisecond per claim

---

## 5. The design decisions you must not accidentally undo

Each of these was found by measuring, not by reading code. Every one has a test.

1. **ADR-0027 — `Evidence.strength` is a 0..1 confidence, not a log-odds delta.**
   It is converted by the calibrated `aggregation.log_odds_per_unit_strength`.
   Before this, the verdict bands described a region the system could not enter:
   every mechanism unit test passed while the whole product returned UNVERIFIED
   for everything.

2. **ADR-0028 — TRUE requires a confirming source.** Only `InstitutionalSource`
   and `OfficialChannel` may confirm. *Absence of fraud indicators is not
   evidence of authenticity* — it is equally consistent with a well-made scam.
   Enforced **structurally**, not by a strength cap: a cap only binds at one
   particular scale and would silently switch off on recalibration.

3. **ADR-0026 — `cannot_conclude_alone: [StrainPrior]`.** Cross-institution
   history can shorten an investigation but can never *be* one. One campus's
   mistake must not become every campus's verdict.

4. **Calibration constraint `scale × 2 ≤ max_abs_log_odds`.** If one agent can
   reach the ±6.0 clamp alone, every other agent is arithmetically discarded and
   the nine-agent cascade is theatre. Currently binding exactly (3.0 × 2 = 6.0).

5. **Asymmetric cascade exit.** Exiting toward FALSE is an accusation; exiting
   toward UNVERIFIED is a decision to stop spending. Different bars.

6. **The cascade may not exit on the reassuring side while a confirming agent is
   still unrun.** Otherwise TRUE is unreachable in practice while looking
   perfectly reachable in config. The guard is **one-directional** — a claim
   heading toward FALSE has no reason to wait.

7. **Negation-aware payment detection.** "No registration fee" is the phrase
   *genuine* notices use to distinguish themselves from scams. Matching it as a
   payment demand was the shortest path to libelling the placement cell.
   Negated phrases are excised before searching, so "no hidden charges … pay
   Rs 750" still fires.

8. **A bare amount is not a payment demand.** "Package: 12 LPA" is an amount too.

9. **A genuine domain beside a fake one earns no credit.** Good phishing quotes
   the real site next to its own; crediting it lets the attacker buy trust with
   the victim's own evidence.

10. **Safe Browsing "no match" is never `supports`.** Blocklists lag by days;
    campus scam links are hours old. `URLSafety` has no supporting path at all.

11. **An unverified `payments` profile block cannot produce an accusation.**
    Naming a real person's UPI handle as fraudulent because nobody filled in a
    YAML file is the most defamatory thing HERD could do.

12. **Degraded ≠ clean.** An agent that found nothing *and* had its network half
    fail returns `unavailable`, not "nothing anomalous found". Collapsing those
    lets a silent outage look like a clean bill of health.

---

## 6. Known gaps — read before trusting any number

**The fixture corpus has no domain-impersonation scam.** Every synthetic scam
uses `bit.ly` and a `.invalid` institution domain. `tools/eval_tier0.py
--with-tier1` now prints this explicitly:

```
URLSafety          spoke on 0/35 claims   <- silent on this corpus
```

Domain impersonation (`vnrvjiet-placements.online`) is the **most common real
campus scam shape** and the entire reason `DomainForensics` exists. It is
covered by unit tests in `tests/test_tier1.py` but **not by the corpus**, so the
37% exact-match number understates the system and the corpus does not yet
exercise Tier 1's strongest rule.

**Fix this first tomorrow** — add ~5 impersonation fixtures, then re-run
`tools/calibrate_aggregation.py`.

Other gaps:
- `app/wiring.py:build_container` **does not exist**, though every ABC docstring
  names it as its construction site. Nothing is assembled end to end yet.
- `app/telemetry.py` exists but has never been imported.
- `web/` is empty. No UI at all.
- No API surface, no ingest endpoint, no spread model, no alerting.
- `tools/lint_excepts.py`, `tools/task_state.py`, `tools/run_acceptance.py`,
  `tools/seed.py` are all still missing.
- Exact-match is 37% at Tier 0+1. That is **fine and expected** — Tier 2 exists
  to settle the remainder — but it is not a demo number yet.

---

## 7. Next steps, in order

1. **Add impersonation fixtures** (§6). Re-run calibration. This is the highest
   ROI single action available.
2. **`app/wiring.py:build_container`** + `tools/check_wiring.py`. Nothing can be
   demoed until the parts are assembled.
3. **Tier 2 agents** — `InstitutionalSource` (snapshot RAG over a pre-crawled
   copy of the college site, ADR-0015) and `OfficialChannel`. These are the only
   agents that can produce TRUE, so **without them the product can never
   confirm anything**. This is the biggest functional hole.
4. **Tier 3** `OpenWebResearch` (LLM, terminal tier).
5. **Verdict prose** — written *after* the label is fixed, with a post-check
   that every entity in `reasoning` appears in the evidence set.
6. **Ingest API** with 60 s idempotency on `image_sha256` + reporter hash.
7. **Spread model** — tiered by sample size (n<5 none / ≤20 Bayesian exp /
   ≤60 logistic / >60 SEIR-Hawkes), observation bias, expected-harm alerting.
8. **Delivery** — Telegram + WebSocket, inoculation card.
9. **React UI** — frozen design tokens, six showpiece components, then the
   visual critique loop to a rubric score ≥90.
10. **Gates** — demo invariant with network blocked, latency gate, cost-curve
    gate, adversarial suite, chaos, portability proof.

The full task graph is `HERD-BUILD-LOOP-v3.md` Block 6 (T001–T107).

---

## 8. How to run things

```powershell
$h = "$env:USERPROFILE\Desktop\v\hackathon"; Set-Location $h

# tests
& "$h\venv\Scripts\python.exe" -m pytest tests\ -q

# corpus evaluation, Tier 0 only / Tier 0+1 with network blocked
& "$h\venv\Scripts\python.exe" tools\eval_tier0.py
& "$h\venv\Scripts\python.exe" tools\eval_tier0.py --with-tier1

# recalibrate the aggregator (add --write to update config)
& "$h\venv\Scripts\python.exe" tools\calibrate_aggregation.py

# commit + push (the only sanctioned path)
pwsh -NoProfile -File tools\push.ps1 -Message "your message"
```

`tests/test_strain.py` takes ~85 s (it loads a sentence-transformer). Everything
else is under 2 s.

---

## 9. Map of the code

```
app/
  contracts.py        FROZEN. Every dataclass, with validators that have caught
                      real bugs twice. Read this before writing anything.
  interfaces.py       FROZEN. 8 ABCs. InvestigationAgent.run() returns ONE
                      Evidence — which is why agents net internally.
  config.py           get_settings() / get_thresholds(). Unknown keys RAISE.
  institution.py      The single door institutional facts come through.
  perceive/
    redact.py         redact_text(text) -> (str, list[str])
    extract.py        deterministic_extract(text, *, report_id, institution_id,
                      claim_id) -> Claim. Emails/UPI are excised before URL
                      scanning so local-parts are not mistaken for hosts.
  recognise/strain.py Incremental strain assignment, ADR-0007/0008 hard gates.
  investigate/
    aggregate.py      THE ONLY PLACE A LABEL IS DECIDED. Correlation-group
                      discounting, then structural downgrades. Single
                      construction site: Aggregator.from_thresholds().
    cascade.py        Tier orchestration, asymmetric exit, deadline (not
                      timeout), enforces "no agent raises" from the outside.
    agents/
      _common.py      Domain arithmetic + Finding/net() shared by tier1+.
      tier0.py        FraudHeuristics, TemplateProvenance
      memory.py       StrainPrior  (ADR-0026 scope boundary lives here)
      tier1.py        DomainForensics, URLSafety, ContactForensics
  storage/sqlite_store.py
  clients/http.py     HttpxFetcher / BlockedFetcher / build_fetcher(mode)
config/
  thresholds.yaml     EVERY tunable. No literal may appear in code.
  fraud_rules.yaml    8 contradicting + 2 supporting rules, each with a
                      correlation_group.
  institutions/       Per-college profiles. _template.yaml to add one.
docs/adr/             28 ADRs. README.md is the index.
tools/
  push.ps1            The only sanctioned push path.
  eval_tier0.py       Corpus confusion matrix. Demo headline numbers.
  calibrate_aggregation.py   4-stage constrained sweep. Records why v1-v3
                      objectives were wrong — read the comments before changing
                      the objective.
tests/
  fakes.py            In-memory doubles that SUBCLASS the ABCs on purpose.
```

---

## 10. Commit history

| Commit | Content |
|---|---|
| `3d41711` | Root commit (orphan; history purged of AI attribution) |
| `3699dd9` | 9 design docs + 26 ADRs |
| `33495f9` | ADR-0026 + institution profiles |
| `7aac122` | P0 foundation — contracts, interfaces, config, locked deps |
| `48dc2c0` | P2 fixtures — 35 synthetic screenshots + labels |
| `213cc47` | P3 perceive — redaction, extraction, telemetry |
| `87d3450` | P4 — storage, strain recognition, threshold calibration |
| `7d05219` | P5a — evidence aggregation + Tier-0 agents |
| `8ee3564` | P5b — tiered cascade + StrainPrior |
| *this one* | P5c — Tier-1 agents, HTTP port, test doubles, extraction fix |
