# API

Small surface by design. Three verbs matter: submit, observe, subscribe.

Base: `/api/v1`

---

## Submit

### `POST /reports`
`multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| `image` | one of image/text | screenshot |
| `text` | one of image/text | pasted message |
| `channel` | yes | `web \| telegram \| share_intent` |
| `cohort` | no | volunteered, e.g. `{"year":3,"branch":"CSE"}` |
| `claimed_source` | no | free text, e.g. "class group" |

Returns **immediately** with a tracking handle rather than blocking on the
investigation — a new strain can take 20 s and the user must not stare at a
spinner.

```json
{
  "report_id": "01J...",
  "strain_id": "01J...",
  "recognised": true,
  "verdict": { "label": "FALSE", "confidence": 0.94, "headline": "...", "...": "..." },
  "stream": "/api/v1/stream/01J..."
}
```

- `recognised: true` → verdict is present, served from herd memory in < 300 ms.
- `recognised: false` → `verdict` is `null`; subscribe to `stream` to watch the
  investigation run live.

**Idempotency:** identical `image_sha256` from the same reporter within 60 s
returns the original report rather than inflating the spread curve. Deduplication
happens before the report ever reaches the spread model.

---

## Observe

### `GET /strains/{id}`
Full public record: canonical claim, verdict with all evidence and sources,
mutation tree, report timeline, spread estimate with caveats.

### `GET /strains?status=&since=&min_reports=`
Paginated list for the dashboard.

### `GET /strains/{id}/tree`
Mutation tree as nodes + edges, with `dominant_signal` on each edge — this is what
the force-directed graph renders.

### `GET /strains/{id}/spread`
`SpreadEstimate`. Every projected quantity is an interval, never a scalar
([Data model](02-data-model.md)).

### `GET /metrics/herd`
The compounding argument, as live numbers:

```json
{
  "strains_total": 214,
  "reports_total": 8431,
  "cache_hit_rate": 0.961,
  "investigations_saved": 8217,
  "marginal_cost_per_report_usd": 0.0009,
  "median_recognition_ms": 180,
  "median_lead_time_hours": 5.2
}
```

`marginal_cost_per_report_usd` falling over time is the whole thesis, exposed as
an endpoint so it can be charted rather than claimed.

---

## Subscribe

### `POST /subscriptions`
```json
{ "channel": "telegram|webpush|email", "token": "...", "cohort": {...},
  "threshold": "all|high_harm_only" }
```

### `GET /alerts?since=`
Alert history, including **suppressed** alerts with `suppressed_reason`.
Publishing suppressions is deliberate: an alerting system that hides its
non-decisions cannot be audited for fatigue policy.

---

## Streams

### `WS /stream/{strain_id}`
Live investigation trace. This is what makes the cascade legible on screen.

```json
{"t":"tier_start","tier":0}
{"t":"agent_start","agent":"FraudHeuristics"}
{"t":"evidence","agent":"FraudHeuristics","signal":"contradicts","strength":0.85,
 "finding":"Upfront fee of ₹750 requested for a job application","elapsed_ms":28}
{"t":"tier_exit","tier":0,"reason":"decisive","posterior":0.93}
{"t":"verdict","label":"FALSE","confidence":0.94}
```

### `WS /stream/firehose`
All strain and alert events. Powers the live wire and the strain map.

---

## Conventions

- **Errors** are RFC 7807 problem documents.
- **Time** is RFC 3339 UTC everywhere.
- **IDs** are ULIDs — time-sortable, which the spread model depends on.
- **Rate limits** are per reporter hash, and a limited reporter still has their
  report counted for spread purposes even when the response is throttled. Rate
  limiting must never blind the epidemic model.
- **Degraded mode** is advertised, not hidden: responses carry
  `X-HERD-Mode: live|degraded|replay` and any verdict produced while a dependency
  was unavailable lists that in `evidence[].status`.
