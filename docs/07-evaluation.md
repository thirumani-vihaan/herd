# Evaluation

A system like this can look impressive and be useless. These are the measurements
that distinguish the two.

## What HERD is optimising

Not accuracy. **Harm prevented per unit of trust spent.**

Accuracy is necessary but insufficient: a system that is 99% accurate and always
answers after the peak prevents nothing. The three axes that matter are
*correctness*, *timeliness*, and *cost*, and a real evaluation reports all three
together, because each is trivially gamed by sacrificing the others.

---

## 1. Correctness

Measured on a held-out labelled corpus (below).

| Metric | Target | Why this one |
|---|---|---|
| **Precision on `FALSE`** | > 0.97 | The number that protects credibility. A false accusation is the failure mode that ends the project. |
| Recall on `FALSE` | > 0.80 | Misses are recoverable; the claim simply sits `UNVERIFIED`. |
| **False `FALSE` on genuine notices** | ≈ 0 | Tracked separately because it is the most damaging single error. |
| Abstention rate | 0.15 – 0.35 | Below this the system is overconfident; above it, useless. |
| Calibration (ECE) | < 0.08 | A stated 0.8 confidence must be right ~80% of the time or the number is decoration. |

Calibration is reported as a reliability diagram, not a single scalar. A system
whose confidence values are uncalibrated is worse than one that reports no
confidence at all, because users reasonably act on the number.

## 2. Timeliness

The axis most detection systems never report, and the one HERD exists for.

| Metric | Meaning |
|---|---|
| **Lead time** | Hours between alert firing and observed peak. Negative means failure. |
| Time-to-first-verdict | First report → published verdict, by tier. |
| Recognition latency | p50/p95 for cache-hit reports. Target p95 < 300 ms. |
| Coverage-at-alert | Fraction of the eventually-affected population still unreached when the alert fired. |

**Coverage-at-alert is the honest headline.** Lead time in hours flatters a slow
rumour; the fraction of people still reachable is what actually determines
prevented harm.

## 3. Cost

This is where the compounding thesis is either true or marketing.

| Metric | Meaning |
|---|---|
| **Cache hit rate** | Fraction of reports resolved from herd memory without investigation. |
| **Marginal cost per report** | Total spend ÷ reports. Must *fall* as volume rises. |
| Cost per new strain | Should be roughly flat. |
| Tier distribution | What fraction of new strains exit at Tier 0/1/2/3. |

The claim "the wider it spreads, the cheaper it gets to neutralise" is a
falsifiable prediction about the marginal-cost curve, and it is plotted rather
than asserted. If that curve is flat, the central thesis is wrong and the
dashboard will show it.

---

## Ground truth

The hardest part of the project, and the part most systems skip.

### Corpus construction

| Class | Source | Notes |
|---|---|---|
| Confirmed false | Scams later publicly identified; cyber-cell advisories; college warnings | The reliable positive class |
| **Confirmed true** | Real institutional notices, real drives, real fee deadlines | Deliberately over-sampled |
| Ambiguous | Partially-true claims — real drive, wrong date | Where systems actually fail |
| Adversarial | Manual mutations of known scams — company swapped, amount changed, poster recoloured | Tests strain matching directly |

The true class is over-sampled on purpose. A corpus that is 90% scams produces a
model that has learned to say "scam", scores beautifully, and is dangerous in
production.

### Labelling
Two independent labellers, disagreements adjudicated, inter-annotator agreement
reported. A corpus without a published agreement number is an opinion.

### Temporal split
Train/tune on earlier data, evaluate on later. Random splits leak template
knowledge across the boundary and inflate results — the adversarial mutation set
makes this leakage severe, so the split must be temporal.

---

## Component evaluation

System metrics hide which part is broken.

| Component | Measured by |
|---|---|
| OCR + extraction | Field-level accuracy on hand-labelled screenshots, worst-case reported per language mix |
| Strain matching | Precision/recall of same-strain pairs against the adversarial mutation set; threshold chosen from the actual PR curve, not guessed |
| Individual agents | Per-agent precision when signal ≠ neutral. Feeds the reliability weights used in aggregation. |
| Aggregator | Compared against best-single-agent and unweighted-vote baselines. If it cannot beat them, it is complexity with no payoff. |
| Spread model | Backtested: fit on the first k reports, compare projected peak against the observed one |

Agent reliability weights being *learned from this table* rather than
hand-assigned is what keeps the aggregator honest as agents are added.

---

## Adversarial evaluation

Assume an attacker who knows exactly how HERD works.

| Attack | Defence | Test |
|---|---|---|
| Paraphrase to evade strain matching | Multilingual embeddings + entity matching | LLM-generated paraphrase suite at increasing distance |
| Fresh domain per campaign | Domain age is only one signal among many | Ablation: performance with `DomainForensics` disabled |
| Aged/hijacked domain | TLS cert age + content history | Simulated |
| Brigading to force an alert | Distinct-reporter velocity; verdicts independent of volume | Simulated coordinated reporting |
| Prompt injection in the screenshot | Extraction output is schema-validated; LLM cannot set the label | Corpus of screenshots containing injected instructions |

The prompt-injection case is worth stating plainly: the input to this system is
attacker-controlled text, so the design rule that **the LLM never decides the
label** is a security control, not a stylistic one
([ADR-0013](adr/0013-deterministic-verdict-aggregation.md)).

---

## Continuous evaluation

Feedback from inoculation cards ("useful" / "already seen this") flows back as
weak labels. *Already seen* is the only unbiased estimator of the reporting rate
available to the system, which makes it the one signal that can validate the
spread model's assumptions in production rather than in backtest.
