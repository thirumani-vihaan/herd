# SPEC_DIGEST — extracted invariants

Machine-checkable extraction of every threshold, budget, and invariant in
`docs/` (9 documents) and `docs/adr/` (27 ADRs). This file is the implementation
checklist. Where an implementation disagrees with this file, the implementation
is wrong.

Source ADRs referenced: 0001 0002 0003 0004 0005 0006 0007 0008 0009 0010 0011
0012 0013 0014 0015 0016 0017 0017a 0018 0019 0020 0021 0022 0023 0024 0025 0026.

---

## 1. Latency budgets (docs/01 §Latency budget)

| Path | Budget | Breakdown |
|---|---|---|
| Recognised report (cache hit) | **< 300 ms** | embed 40 · search 15 · entity check 5 · render 200 |
| New strain, Tier 0 conclusive | **< 2 s** | + rules 30 ms · prose 1.5 s |
| New strain, full cascade | **< 20 s** | + lookups 3 s · retrieval 2 s · synthesis 4 s · slack 10 s |
| Alert fan-out | **< 1 s** | WS broadcast + Telegram batch |

Enforced by T102. p95, not mean.

## 2. Strain assignment thresholds (ADR-0007)

| Cosine to nearest centroid | Action |
|---|---|
| ≥ 0.88 | Same strain — attach, serve cached verdict |
| 0.72 – 0.88 | Mutation — child strain linked to parent |
| < 0.72 | New strain — full investigation |

Similarity = **max over both vectors** (native, `text_en`) — ADR-0006.
Thresholds live in `config/thresholds.yaml`, never in code. Calibrated in T044
from the actual PR curve; if the data disagrees, the data wins and an ADR is
written.

## 3. Entity gates (ADR-0008)

Same strain requires cosine ≥ 0.88 **AND** all hard gates pass.

- **Hard:** `organisations` (set equality after alias normalisation),
  `amounts` (within 20%), registrable domain.
- **Soft:** dates, locations — differences allowed, recorded in `MutationDiff`.
- Hard-gate failure at high similarity ⇒ **sibling strain**, surfaced as evidence.

## 4. Cascade (ADR-0011, docs/03)

| Tier | Agents | Cost | Exit \|posterior\| |
|---|---|---|---|
| 0 | FraudHeuristics, TemplateProvenance | free ~30 ms | > 0.90 |
| 1 | DomainForensics, URLSafety, ContactForensics | free-tier ~1–3 s | > 0.85 |
| 2 | InstitutionalSource, OfficialChannel | local index ~2–4 s | > 0.80 |
| 3 | OpenWebResearch | LLM ~3–5 s | — |

Parallel within a tier, sequential across tiers.
**Asymmetric exit:** exiting toward `FALSE` requires more strength than exiting
toward `UNVERIFIED`.

### Agent contract (4 rules, docs/03)
1. Return `Evidence`, never a verdict (ADR-0012).
2. Cite or stay silent — any non-neutral finding carries ≥1 `Source` with URL and
   retrieval timestamp.
3. **Never raise.** Failure ⇒ `status=unavailable`.
4. Declare applicability — `not_applicable` returns immediately and costs nothing.

## 5. Fraud rules (docs/03) — `config/fraud_rules.yaml`, versioned

| Rule id | Signal | Strength |
|---|---|---|
| `upfront_fee_for_job` | contradicts | 0.85 |
| `personal_messaging_contact_only` | contradicts | 0.60 |
| `personal_upi_vpa` | contradicts | 0.80 |
| `deadline_under_48h` | contradicts | 0.35 |
| `url_shortener_on_official_link` | contradicts | 0.50 |
| `sender_domain_mismatch` | contradicts | 0.70 |
| `freemail_corporate_recruiting` | contradicts | 0.55 |
| `limited_slots_register_now` | contradicts | 0.30 |

Each rule cites itself. Weights in config, not code.

## 6. Aggregation (ADR-0013)

```
Δ log-odds = signal_direction × strength × agent_reliability
```

**Correlation groups: within a group only the strongest signal counts at full
weight; the rest are discounted.** Without this the posterior saturates at 0.99.

| Posterior P(false) | Label |
|---|---|
| > 0.90 | `FALSE` |
| 0.65 – 0.90 | `MISLEADING` |
| 0.20 – 0.65 | `UNVERIFIED` |
| < 0.20 | `TRUE` |

`UNVERIFIED` is the widest band on purpose. Target abstention rate **0.15–0.35**
(ADR-0014).

### Encoded asymmetries — each is a test
- `URLSafety` non-hit contributes **exactly 0.0**.
- `InstitutionalSource` contradiction strength **capped**; support **uncapped**.
- `OfficialChannel` same shape, higher contradiction cap.
- Cross-institution `StrainPrior` is bounded and **cannot alone reach a band**
  (ADR-0026).

## 7. The LLM's job (ADR-0013)

Label and confidence are fixed **before** the LLM is called. It writes
`headline`, `reasoning`, `what_would_change_my_mind` only, introduces no new
facts. Post-check: every entity in `reasoning` must appear in the evidence set →
else retry → else deterministic template.

This is a **security control**: the input is attacker-controlled, so prompt
injection must not be able to reach the label.

## 8. Spread model (ADR-0017, ADR-0018)

| Reports n | Model |
|---|---|
| < 5 | **None.** No curve, no projection. |
| 5 – 20 | Bayesian exponential growth |
| 21 – 60 | Logistic |
| > 60 | SEIR / Hawkes branching |

- Model in use is **displayed**. Never upgraded because it looks better.
- Use **message time** (`ForwardMarkers.visible_timestamp`) where available,
  report time otherwise, and widen intervals when unavailable.
- Every projected quantity is an `Interval`, never a float. Enforced at schema
  level.
- `caveats` rendered verbatim, never summarised away.
- `scipy` fits are wrapped: never crash, never fabricate. Fit failure ⇒ downgrade
  the tier and say so.

## 9. Alerting (ADR-0019)

Expected-harm maximisation, **not** a threshold:

```
alert iff  E[harm prevented] > E[harm caused]
```

- Fatigue is a **cost term inside the rule**, not a bolted-on suppressor.
- `unreached ≈ 0` ⇒ never alert, regardless of confidence.
- Suppressed alerts are **published with their reason**.

## 10. Intervention (ADR-0020)

Inoculation card: **exactly 2** evidence items, names **the technique** (not just
the instance), and carries an action path for the already-harmed.
Framing is pre-bunk, never debunk. Wording is evidence-only, never accusation
(ADR-0025).

## 11. Evaluation targets (docs/07)

| Metric | Target |
|---|---|
| **Precision on `FALSE`** | **> 0.97** |
| Recall on `FALSE` | > 0.80 |
| False-`FALSE` on genuine notices | ≈ 0 |
| Abstention rate | 0.15 – 0.35 |
| Calibration ECE | < 0.08 |
| Recognition p95 | < 300 ms |

Corpus: TRUE class **≥ 35%** (T021). A corpus that is 90% scams trains a model
that says "scam", scores beautifully, and is dangerous.

## 12. Privacy & identity

- Report-driven only. Never joins a group, never reads a chat (ADR-0001).
- Reporter identity = **rotating salted HMAC**, 30-day rotation, raw identifier
  never persisted (ADR-0004).
- **Screenshot redaction happens at ingest, before persistence** — not before
  display. Redacting before display does not survive a DB breach.
- Idempotency: identical `image_sha256` + reporter within **60 s** collapses to
  one report, *before* the spread model sees it.

## 13. Scope (ADR-0024, docs/09)

In scope: institutional/administrative claims — placements, fees, exams,
scholarships, schedules, campus events.
Out of scope, **refused as an outcome**: politics, health, general news, personal
disputes. Refusal is a first-class verdict, not an error.

## 14. Multi-tenancy (ADR-0026)

- `institution_id` **required** on `Report`, `Evidence`, `Verdict`,
  `SpreadEstimate`, `Alert`, `Cohort`.
- `Strain` has **no** `institution_id` — strain memory is global.
- Cross-institution sighting ⇒ one bounded `StrainPrior` signal in its own
  correlation group. Can shorten an investigation; can never produce a verdict.
- Zero institutional strings in `app/**`, `web/**`, or any prompt (L13).
- Falsifiable test (T107): switch `HERD_INSTITUTION`, run the full demo, **zero
  code changes**.

## 15. Degradation (ADR-0023, docs/01 §Failure model)

| Dependency down | Behaviour |
|---|---|
| LLM | Deterministic template verdict; label unaffected (label was never the LLM's) |
| Safe Browsing | Evidence `unavailable`, strength 0 |
| RDAP | Evidence `unavailable` |
| Institutional site | Pre-crawled snapshot (ADR-0015) |
| Network entirely | `DEMO_MODE=replay`, cassettes, everything still works |

`X-HERD-Mode` header is **always** set. Every degraded state is visible in the
UI, never silent.

## 16. Non-negotiable invariants (fail the build)

1. No fabricated data anywhere; fixtures carry `is_fixture=True` and render a
   `FIXTURE` chip.
2. `Verdict.what_would_change_my_mind` is non-empty — schema-enforced.
3. Every projected quantity is an `Interval`.
4. No agent raises; no bare `except: pass`.
5. Strain IDs are stable forever; consolidation merges by alias, never renames.
6. The demo invariant passes with the network blocked, after every task.
