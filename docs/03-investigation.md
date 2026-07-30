# Investigation

## The cascade

The first design of this layer fanned out to every agent in parallel on every new
strain. That is wrong for three reasons: it spends LLM tokens on claims a
five-line rule engine can settle, it makes p95 latency equal to the slowest
dependency, and it produces a cost curve that grows with attack volume — exactly
the property HERD exists to invert.

So the investigation is a **cascade with early exit**
([ADR-0011](adr/0011-tiered-investigation-cascade.md)). Each tier is parallel
*within* itself; tiers run in sequence and stop as soon as the accumulated
evidence is decisive.

```
 Tier 0  deterministic          ~30 ms      free
   |     fraud rules, URL shape, UPI/fee detection, pHash lookup
   |     exit if |score| > 0.9
   v
 Tier 1  cheap networked        ~1-3 s      free-tier APIs
   |     RDAP domain age, Safe Browsing, TLS cert age, DNS
   |     exit if |score| > 0.85
   v
 Tier 2  retrieval              ~2-4 s      local index + 1-2 fetches
   |     institutional snapshot RAG, official careers page
   |     exit if |score| > 0.8
   v
 Tier 3  synthesis              ~3-5 s      LLM
         open-web reasoning, cross-source reconciliation
```

Observed distribution in practice: the large majority of *reports* never reach
Tier 1 because they are cache hits at the recognise stage; of genuinely new
strains, obvious fee-scams settle at Tier 0, and Tier 3 is reserved for claims
that are ambiguous rather than merely unfamiliar.

**The exit threshold is asymmetric.** Exiting early with `FALSE` requires more
accumulated strength than exiting with `UNVERIFIED`, because the cost of a false
accusation is much higher than the cost of a slow answer
([ADR-0014](adr/0014-calibrated-confidence-and-abstention.md)).

---

## Agent contract

Every agent implements:

```
async def run(claim: Claim, context: StrainContext) -> Evidence
```

and obeys four rules:

1. **Return evidence, never a verdict.** An agent may say "the careers page lists
   no such drive"; it may not say "this is fake."
   ([ADR-0012](adr/0012-evidence-not-verdicts.md))
2. **Cite or stay silent.** Any `finding` with `signal != neutral` must carry at
   least one `Source` with a URL and a retrieval timestamp.
3. **Never raise.** Failure returns `status=unavailable`, never an exception.
4. **Declare applicability.** An agent that has nothing to say for this claim
   type returns `not_applicable` immediately and costs nothing.

---

## Agents

### Tier 0 — deterministic

#### `FraudHeuristics`
Pure rule engine, no model. Each rule is individually named, individually
weighted, and cites *itself* as its source, so the reasoning shown to the user is
auditable line by line.

| Rule | Signal | Strength | Rationale |
|---|---|---|---|
| Upfront fee for a job application | contradicts | 0.85 | Legitimate employers do not charge candidates. Near-conclusive. |
| Contact only via personal Telegram/WhatsApp | contradicts | 0.6 | Real drives route through institutional or corporate channels. |
| Payment to a personal UPI VPA | contradicts | 0.8 | |
| Deadline < 48 h from first sighting | contradicts | 0.35 | Manufactured urgency; weak alone, common in combination. |
| URL shortener on an "official" link | contradicts | 0.5 | |
| Sender domain ≠ claimed organisation domain | contradicts | 0.7 | |
| Free-mail address for corporate recruiting | contradicts | 0.55 | |
| "Limited slots" + "register now" template pair | contradicts | 0.3 | |

Weights are not vibes — they are estimated from the labelled corpus and
recalibrated as it grows ([Evaluation](07-evaluation.md)). They are stored in a
versioned config file, not in code.

#### `TemplateProvenance`
Perceptual hash of the poster against the known-template store. A hit means this
exact artwork has been seen before under a different company name — the single
most diagnostic signal HERD has, because it demonstrates industrial reuse rather
than a one-off. Uses pHash for near-duplicate detection and a CLIP embedding as a
secondary channel for recoloured/recropped variants
([ADR-0009](adr/0009-mutation-detection.md)).

### Tier 1 — cheap networked

#### `DomainForensics`
RDAP ([ADR-0016](adr/0016-rdap-over-whois.md)) for registration date and
registrar, plus TLS certificate issuance date. A domain registered days before a
"campus placement drive" is strong evidence. Handles the obvious confound: a
young domain is *not* suspicious for a genuinely new startup, so strength is
modulated by whether the claimed organisation is established.

#### `URLSafety`
Google Safe Browsing lookup. High strength when it fires, explicitly **zero**
strength when it does not — absence of a listing is not evidence of safety, and
the aggregator must not treat it as such. This asymmetry is encoded, not assumed.

#### `ContactForensics`
Phone number carrier/circle lookup and UPI VPA handle inspection. A "TCS HR"
number on a prepaid connection from an unrelated circle is a real signal.

### Tier 2 — retrieval

#### `InstitutionalSource`
RAG over a pre-crawled snapshot of the institution's notices, circulars, and
placement pages ([ADR-0015](adr/0015-institutional-snapshot.md)). Answers "has
the college actually announced this?"

The subtlety: **absence in the notice board is weak evidence, not strong.**
Colleges announce things late and inconsistently. This agent's strength is capped
for `contradicts` and uncapped for `supports` — finding the official notice
settles the question; not finding it does not.

#### `OfficialChannel`
For a named organisation, fetch its real careers/press page and check for the
claimed drive. Same asymmetry as above, with a higher contradiction cap: a large
employer's careers page is a far more complete record than a college notice board.

### Tier 3 — synthesis

#### `OpenWebResearch`
LLM with retrieval over general web results, used only for genuinely ambiguous
claims. Constrained to quote-and-cite: it may only report what a retrieved
document says, and every sentence in its `finding` must map to a `Source`.

---

## Aggregation

The label is **not** produced by a language model
([ADR-0013](adr/0013-deterministic-verdict-aggregation.md)).

Evidence is combined in log-odds space. Each agent contributes

```
Δ log-odds = signal_direction × strength × agent_reliability
```

where `agent_reliability` is a per-agent multiplier learned from the labelled
corpus and updated as ground truth accumulates. Agents that have historically
been wrong are automatically down-weighted; no code change required.

The posterior is mapped to a label through calibrated bands, with a deliberate
abstention region:

| Posterior probability of falsity | Label |
|---|---|
| > 0.90 | `FALSE` |
| 0.65 – 0.90 | `MISLEADING` |
| 0.20 – 0.65 | `UNVERIFIED` |
| < 0.20 | `TRUE` |

`UNVERIFIED` occupies the widest band on purpose. A system that is confidently
wrong once loses the trust that took a hundred correct calls to earn.

### Correlated evidence

Naive log-odds addition assumes independence, which is false here: "URL
shortener", "young domain", and "free-mail sender" all co-occur in the same
attack kit. Independent summation would over-count and manufacture false
certainty.

Agents are therefore assigned to **correlation groups**, and within a group only
the strongest signal contributes at full weight; the rest are discounted. This
single detail is the difference between a calibrated system and one that always
outputs 0.99.

### The LLM's actual job

After the label and confidence are fixed by aggregation, the LLM writes:
- `headline` — one plain-language line
- `reasoning` — prose over the evidence, introducing **no new facts**
- `what_would_change_my_mind` — the falsifier

A post-generation check verifies that every entity mentioned in `reasoning`
appears in the evidence set. If it does not, generation is retried, then falls
back to a deterministic template. The model is a writer here, not a judge.
