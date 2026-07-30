# Data Model

Every boundary in the system is a validated Pydantic model. Nothing untyped
crosses a layer.

## Entity relationships

```
Reporter (pseudonymous)
    |
    | submits
    v
Report ---------> Claim ---------> Strain <----- Verdict
  (raw)          (structured)     (cluster)         ^
                                      |             |
                                      |             | built from
                                      v             |
                                 SpreadEstimate   Evidence[]
                                      |
                                      v
                                    Alert
```

One `Strain` has many `Report`s, exactly one current `Verdict`, one rolling
`SpreadEstimate`, and zero or more `Alert`s. A `Strain` may have a parent strain
(it is a mutation of it).

---

## Report

The raw artifact a human handed us. Immutable.

| Field | Type | Notes |
|---|---|---|
| `id` | `ULID` | time-sortable; ordering matters for the spread model |
| `received_at` | `datetime` | server clock, UTC |
| `channel` | `web \| telegram \| share_intent \| api` | |
| `raw_text` | `str \| None` | if pasted/forwarded as text |
| `image_sha256` | `str \| None` | content address of the screenshot |
| `image_phash` | `str \| None` | perceptual hash, for template matching |
| `reporter_hash` | `str` | salted, rotating — see ADR-0004 |
| `forward_markers` | `ForwardMarkers` | parsed from screenshot chrome |
| `claimed_source` | `str \| None` | "got it in CSE-A group" if volunteered |

### ForwardMarkers

Extracted from the screenshot UI, not from the message body. This is the only
spread signal available without surveillance.

| Field | Type | Notes |
|---|---|---|
| `is_forwarded` | `bool \| None` | |
| `is_frequently_forwarded` | `bool \| None` | WhatsApp's "forwarded many times" |
| `visible_timestamp` | `time \| None` | message time shown in the screenshot |
| `group_size_hint` | `int \| None` | if a member count is visible |

`visible_timestamp` matters more than it looks: it lets the spread model use
*message* time rather than *report* time, which materially reduces observation
lag (see [ADR-0018](adr/0018-report-process-bias.md)).

---

## Claim

The structured, falsifiable assertion. This is what gets investigated.

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | normalised claim, one sentence |
| `text_en` | `str` | English rendering, for cross-lingual matching |
| `claim_type` | `ClaimType` | see enum below |
| `entities` | `Entities` | |
| `asserted_deadline` | `datetime \| None` | urgency is a fraud signal |
| `money_requested_inr` | `Decimal \| None` | |
| `contact_channels` | `list[str]` | telegram / whatsapp / phone / form |
| `language_mix` | `list[str]` | e.g. `["te","en"]` |
| `extraction_confidence` | `float` | model's own, uncalibrated — advisory only |

### ClaimType

`job_drive` · `exam_schedule` · `fee_deadline` · `event` · `scholarship` ·
`government_scheme` · `lost_and_found` · `safety_alert` · `other`

The type routes the investigation: a `job_drive` triggers the careers-page and
domain agents; an `exam_schedule` triggers the institutional-notice agent. Types
outside this list are refused ([ADR-0024](adr/0024-scope-guard.md)).

### Entities

`organisations` · `people` · `dates` · `amounts` · `urls` · `phones` ·
`upi_ids` · `locations`

Entities are the second half of strain identity. Two claims with identical
templates but different `organisations` are different strains
([ADR-0008](adr/0008-strain-identity.md)).

---

## Strain

A cluster of reports believed to be the same rumour, including its mutations.

| Field | Type | Notes |
|---|---|---|
| `id` | `ULID` | |
| `centroid` | `vector[384]` | running mean of member claim embeddings |
| `canonical_claim` | `Claim` | the clearest observed variant |
| `parent_strain_id` | `ULID \| None` | set if this is a mutation |
| `mutation_diff` | `MutationDiff \| None` | what changed from the parent |
| `first_seen_at` | `datetime` | |
| `report_ids` | `list[ULID]` | |
| `member_count` | `int` | denormalised for the dashboard |
| `verdict` | `Verdict \| None` | |
| `status` | `investigating \| resolved \| stale` | |

### MutationDiff

Mutation is detected across three independent signals so a single noisy channel
cannot invent a branch:

| Field | Meaning |
|---|---|
| `semantic_distance` | cosine distance from parent centroid |
| `entity_changes` | added/removed/substituted entities |
| `image_phash_distance` | Hamming distance of poster hashes |
| `dominant_signal` | which one triggered the branch |

The classic case: the same scam poster recoloured with a different company name.
Text similarity is high, entities differ, pHash distance is tiny — that pattern
alone is near-conclusive evidence of a template scam, and it is surfaced as
evidence, not just as bookkeeping.

---

## Evidence

What an investigation agent returns. Agents never return conclusions
([ADR-0012](adr/0012-evidence-not-verdicts.md)).

| Field | Type | Notes |
|---|---|---|
| `agent` | `str` | |
| `status` | `ok \| unavailable \| not_applicable` | |
| `finding` | `str` | one factual sentence |
| `signal` | `supports \| contradicts \| neutral` | direction only |
| `strength` | `float 0..1` | how diagnostic, not how confident |
| `sources` | `list[Source]` | url + retrieved_at + excerpt |
| `elapsed_ms` | `int` | shown live in the UI |

`signal` and `strength` are separated deliberately. "This domain is 4 days old"
is a *weak-strength contradicting* signal on its own but combines with others;
"the company's official careers page lists no such drive" is *high-strength*.
The aggregator needs both axes.

---

## Verdict

| Field | Type | Notes |
|---|---|---|
| `label` | `FALSE \| MISLEADING \| UNVERIFIED \| TRUE` | set deterministically |
| `confidence` | `float 0..1` | calibrated, see ADR-0014 |
| `headline` | `str` | one line, plain language |
| `reasoning` | `str` | LLM prose over the evidence, no new facts |
| `evidence` | `list[Evidence]` | |
| `what_would_change_my_mind` | `list[str]` | mandatory, non-empty |
| `decided_at` | `datetime` | |
| `decided_by` | `rules \| rules+llm \| human_override` | |

`what_would_change_my_mind` is a required field with a non-empty constraint. A
verdict that cannot state its own falsifier is not allowed to be emitted.

---

## SpreadEstimate

| Field | Type | Notes |
|---|---|---|
| `model` | `exponential \| logistic \| seir` | chosen by sample size |
| `n_reports` | `int` | |
| `velocity_per_hour` | `float` | |
| `reproduction_estimate` | `Interval \| None` | point + credible interval |
| `projected_peak_at` | `Interval \| None` | interval, never a point |
| `estimated_unreached` | `Interval \| None` | |
| `fit_quality` | `float` | |
| `caveats` | `list[str]` | rendered in the UI verbatim |

Every quantity that could be misread as precise is typed as an `Interval`. This
is enforced at the schema level so no display code can accidentally render a
point estimate.

---

## Alert

| Field | Type | Notes |
|---|---|---|
| `strain_id` | `ULID` | |
| `fired_at` | `datetime` | |
| `lead_time_hours` | `float` | vs. projected peak — the headline metric |
| `expected_harm_prevented` | `float` | the decision quantity, ADR-0019 |
| `audience` | `all \| predicted_path` | |
| `channels` | `list[str]` | |
| `message` | `InoculationCard` | |
| `suppressed_reason` | `str \| None` | set if fatigue policy blocked it |
