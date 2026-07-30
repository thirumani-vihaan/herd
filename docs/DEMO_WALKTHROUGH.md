# HERD — Demo Walkthrough

Everything you need to explain, defend and demonstrate HERD. Read this the
night before. The **§9 Q&A** section is the part that wins or loses the room.

> **Status honesty:** as of this document the investigation core is built and
> tested (168 tests). The UI, the API and Tier 2/3 agents are not built yet.
> See `HANDOFF.md` §6. Do not rehearse a demo of something that does not exist —
> rehearse the demo of what *will* exist, and check it against `HANDOFF.md` §7
> the morning of.

---

## 1. The one-sentence pitch

> **HERD is an immune system for campus misinformation.** It doesn't check
> messages — it recognises *strains*, tracks how they mutate and spread, and
> warns the students who haven't been reached yet.

## 2. The 30-second version

Every semester the same fake placement drive goes around WhatsApp. Different
company name, same skeleton: a package too good to be true, a limited-slots
deadline, a shortened link, and a ₹750 "registration fee" to a personal UPI
handle. By the time the placement cell posts a denial, the money is gone.

HERD takes a forwarded screenshot, extracts the claim, and asks: *have I seen
this template before?* — not this message, this **template**. It investigates
with a cascade of agents that get progressively more expensive, stops at the
cheapest one that can settle the question, and produces a verdict where every
number is traceable to a cited source. Then it models how fast the strain is
spreading and warns the cohorts it hasn't reached yet.

**The immune system framing is not a metaphor for the slide.** It is the
architecture: antigen recognition (strain matching), memory cells (`StrainPrior`),
graduated response (the tiered cascade), and inoculation (warning the unreached).

---

## 3. Why this is the unexpected build

Most "fake news detector" projects are one LLM call with a prompt that says
"is this real?". Three things make HERD different, and each is demonstrable:

### 3.1 The verdict is arithmetic. The LLM only writes prose.

The label is decided in `app/investigate/aggregate.py` by log-odds accumulation
over cited evidence. The LLM is invoked **after** the label is fixed, and its
only job is to explain a decision it did not make (ADR-0013).

**Why anyone should care:** the failure mode of LLM fact-checking is confident
fabrication. HERD structurally cannot fabricate a verdict, because the component
that could fabricate is never asked for one. Unplug the LLM entirely and the
labels are byte-identical — only the prose degrades to a template.

### 3.2 It recognises strains, not messages.

A scam mutates constantly — new company, new amount, new URL. HERD assigns each
claim to a **strain** by dual-vector similarity with hard entity gates
(ADR-0007/0008). A mutation becomes a *child* strain that inherits its parent's
history.

**The payoff:** the second college to see the same operation gets an answer in
milliseconds from `StrainPrior`, for free, with no network and no LLM call.
That is the "herd" in HERD — immunity is shared.

### 3.3 It is engineered to refuse.

Abstention is a first-class outcome. On the labelled corpus:

- **0 out of 14 genuine notices were ever accused.**
- **0 claims were confirmed TRUE without a citable source.**

Those are not accidents. They are enforced structurally — see §5.

---

## 4. The live demo (target shape)

Run with the **network physically disconnected** for at least one report. That
is the moment that lands.

| # | Beat | What to say |
|---|---|---|
| 1 | Paste/forward the flagship scam screenshot | "This is the real thing, lightly anonymised." |
| 2 | Verdict appears in well under a second | "That was Tier 0. Free, offline, no model call. It cost nothing." |
| 3 | Open the evidence panel | "Every row cites a rule or a source. Nothing here is an opinion." |
| 4 | Point at the cascade trace | "Three tiers it never had to buy. The median report costs zero." |
| 5 | Feed a **mutated** version — different company, different amount | "Same strain. It's a mutation of what you just saw. Instant, from memory." |
| 6 | Feed a **genuine** placement notice | "UNVERIFIED, not TRUE. It won't confirm without a source that's entitled to confirm. It would rather say 'I don't know' than vouch for something." |
| 7 | **Unplug the wifi. Do it again.** | "Every agent that needs the network degrades and says so. The answer still arrives." |
| 8 | Show the spread curve + inoculation card | "It's not just labelling — it's warning the people who haven't seen it yet." |
| 9 | Switch `HERD_INSTITUTION` to another college and re-run | "Zero code changes. Not a VNR project — a college-agnostic one." |

**Rehearse beat 7 and beat 9.** They are the two that judges remember, and both
are pure configuration, so both are safe to promise.

---

## 5. The five decisions to defend on stage

Judges reward *earned* decisions. Each of these was found by measuring, not by
reading code. All five have tests.

### 5.1 "Absence of fraud indicators is not evidence of authenticity."

**The bug it fixed:** an early calibration run confirmed 13 of 14 genuine
notices as TRUE — on evidence that amounted to *"no fraud rule fired."*

That is worse than being wrong. It is exactly what a **well-made scam** looks
like, and exactly what a credential phish that never mentions money looks like.

**The fix (ADR-0028):** TRUE requires a `supports` finding from an agent
entitled to confirm — one that actually found the notice on the institution's
own source. Enforced **structurally**, not with a strength cap, because a cap
only binds at one particular calibration value and would silently switch itself
off the next time the system was recalibrated.

### 5.2 "No registration fee" was firing the payment-demand rule.

That phrase is what **genuine** notices say to distinguish themselves from
scams. HERD was punishing exactly the text written to reassure people — the
shortest possible path to libelling the placement cell.

**The fix:** negated payment phrases are excised before the rule searches, so
"no hidden charges … pay ₹750" still fires. Worst-case safety margin went from
**0.070 → 0.297**.

### 5.3 The arithmetic was inert and every unit test passed.

`Evidence.strength` is a 0..1 confidence. It was being added directly into a
log-odds accumulator. With a prior of `logit(0.35) = −0.62` and FALSE at
`logit(0.90) = +2.20`, reaching FALSE needed a total delta of 2.82 — impossible
when every agent caps at 1.0.

**The verdict bands described a region the system could not enter.** Every
mechanism test passed. The product returned UNVERIFIED for everything, including
the flagship scam.

**The fix (ADR-0027):** an explicit, calibrated conversion from confidence to
log-odds. 6% → 43% exact match, still zero harmful errors.

*This is the best story in the project.* It shows a class of bug that unit tests
cannot catch, caught by measuring end-to-end behaviour against labelled data.

### 5.4 One agent must not be able to exhaust the clamp alone.

During calibration the objective kept improving as the scale factor rose — until
the realisation that at scale 7.0 a **single** agent hits the ±6.0 log-odds
clamp by itself, making every other agent arithmetically irrelevant.

The nine-agent cascade would have been theatre. A hard constraint
(`scale × 2 ≤ max_abs_log_odds`) now prevents it. It binds exactly today.

### 5.5 One campus's mistake must not become every campus's verdict.

Strain memory is global; evidence is institution-scoped (ADR-0026).
`StrainPrior` reads *this* institution's verdict in full, and for every other
institution reads **only the label on the sighting** — never their evidence,
never their reasoning, never their confidence. And it sits in
`verdict.cannot_conclude_alone`, so cross-campus history can *shorten* an
investigation but can never *be* one.

There is a test that asserts the remote verdict record is **never even read** —
because an agent that fetches it and then declines to use it has already crossed
the boundary, and the next refactor will keep the fetch and drop the declining.

---

## 6. The architecture, in the order you should explain it

```
 report ──▶ PERCEIVE ──▶ RECOGNISE ──▶ INVESTIGATE ──▶ AGGREGATE ──▶ SPREAD ──▶ INTERVENE
            redact       strain         tiered          log-odds      tiered     alert the
            extract      assignment     cascade         over cited    by sample  unreached
                         + mutation     (9 agents)      evidence      size       cohorts
```

**Perceive** — PII is redacted *before* anything else touches the text. Claims
are extracted deterministically; the LLM path is an enhancement, not a
dependency.

**Recognise** — dual-vector similarity (native + normalised English) with hard
entity gates. Differing organisations means a different strain even at 0.99
cosine, because "TCS drive" and "Infosys drive" are different operations however
similar the wording.

**Investigate** — the cascade. Parallel within a tier, sequential across tiers,
stop at the cheapest tier that settles it.

| Tier | Agents | Cost | Exit bar |
|---|---|---|---|
| 0 | FraudHeuristics, TemplateProvenance, StrainPrior | free, ~ms | 0.90 |
| 1 | DomainForensics, URLSafety, ContactForensics | free tier, 1–3 s | 0.85 |
| 2 | InstitutionalSource, OfficialChannel | local index, 2–4 s | 0.80 |
| 3 | OpenWebResearch | LLM, 3–5 s | terminal |

**Aggregate** — the only place a label is decided. Log-odds with
correlation-group discounting, then structural downgrades.

**Spread** — the model is chosen by **sample size, never by how it looks**:
under 5 reports there is no curve and HERD says so. Every projected quantity is
an interval, never a point estimate.

**Intervene** — expected-harm alerting, with alert fatigue as a **cost term
inside the decision rule**, not a suppressor bolted on afterwards.

---

## 7. The numbers to quote

All reproducible with `venv\Scripts\python.exe tools\eval_tier0.py --with-tier1`
on a 35-claim labelled corpus, **with the network blocked**:

| Metric | Value |
|---|---|
| Scams detected | **13 / 13** |
| Genuine notices falsely accused | **0 / 14** |
| Confirmed TRUE without a citable source | **0** |
| Worst-case margin to an error | **0.214** posterior units |
| Offline latency | sub-millisecond per claim |
| Tests | **168 passing** |
| ADRs | **28** |

**Say the caveat out loud before a judge finds it:** exact label match at
Tier 0+1 is 37%, because everything HERD cannot settle offline it *abstains* on
rather than guessing. Tiers 2 and 3 exist to settle those. Abstention is the
designed behaviour, not a shortfall — and 100% of outcomes are "acceptable"
(correct, or an honest abstention).

---

## 8. What is genuinely not built yet

Be straight about this if asked. Judges punish bluffing far harder than
incompleteness.

- Tier 2 (`InstitutionalSource`, `OfficialChannel`) and Tier 3
  (`OpenWebResearch`). **These are the only agents that can confirm a notice as
  TRUE**, so today HERD can catch scams but cannot yet vouch for a genuine
  notice — it abstains instead. That is the safe direction to be incomplete in.
- `app/wiring.py` — the parts are built and tested but not yet assembled.
- Web UI, ingest API, spread model, alert delivery.
- The fixture corpus contains **no domain-impersonation scam**, so
  `DomainForensics`' strongest rule is covered by unit tests but not by the
  corpus. `tools/eval_tier0.py --with-tier1` prints this gap explicitly rather
  than letting it hide inside a passing number.

---

## 9. Questions judges will ask, and the answers

**"Isn't this just ChatGPT with extra steps?"**
The opposite. The LLM never decides anything. The label comes from arithmetic
over cited evidence; the LLM is called afterwards to write prose explaining a
decision it did not make. Unplug it and the labels are identical.

**"What if it's wrong and it accuses a real notice?"**
That is the failure mode the whole system is shaped around. TRUE is unreachable
without a citable source; exiting toward FALSE has a strictly higher bar than
abstaining; per-agent contradiction caps stop any single signal running away.
Measured: 0 out of 14 genuine notices accused, with a worst-case margin of 0.214.
And when it doesn't know, it says UNVERIFIED — it is designed to be uncertain in
public.

**"How is this different from Google's Safe Browsing / a spam filter?"**
Safe Browsing lists a domain days after it is reported. A campus scam link is
hours old, so a blocklist miss is the answer for live scams *and* genuine
notices alike. HERD explicitly refuses to read "not on the blocklist" as
evidence of safety — `URLSafety` has no supporting path at all. What HERD adds
is *institutional context*: it knows what this college's real domains, mail
domains and payment handles are.

**"Does it work for other colleges?"**
Every institutional fact enters through one file. There is no institution string
anywhere in the application code — it is lint-enforced. Switch the environment
variable, get a different college. *(Demo this.)*

**"What about privacy? You're reading students' WhatsApp."**
Nothing is read. A student chooses to forward one screenshot. PII is redacted
before anything else touches it. Reporters are salted hashes with rotation. The
only spread signal used is the forwarding chrome visible in the screenshot
itself — deliberately, because the alternative is surveillance.

**"How do you know your thresholds are right?"**
They aren't guessed. `tools/calibrate_aggregation.py` runs a constrained sweep
over a labelled corpus with hard constraints (never libel, never confirm without
a source, never let one agent exhaust the clamp), a floor on catch rate, and
then maximises the **worst-case margin to an error**. The tool's comments record
why the first three versions of that objective were wrong.

**"What happens when the network dies during the demo?"**
*(Unplug it.)* Every agent that needs the network degrades to `unavailable` and
says so in the UI. Tier 0 is entirely offline and `DomainForensics` keeps its
offline half — a lookalike domain is identifiable from the *string*. The answer
still arrives; it is just less certain, and it tells you it is less certain.

**"Why a tiered cascade instead of running everything?"**
Cost and honesty. The median report is settled by free offline rules, so most
reports cost nothing — that is what makes it deployable at a college's budget.
And the trace shows exactly which tiers were bought, so the cost of an answer is
as auditable as the answer.

**"What's the hardest bug you hit?"**
The arithmetic was inert. `strength` was a 0..1 confidence being added straight
into a log-odds accumulator, so the FALSE band sat at a total the system could
never reach. Every unit test passed; the product returned UNVERIFIED for
everything. It was only visible by measuring end-to-end against labelled data.
*(This answer is your best one — it demonstrates the difference between testing
mechanisms and testing behaviour.)*

---

## 10. Two-minute rehearsal script

> Every semester the same fake placement drive goes around WhatsApp. New company
> name, same skeleton — too-good package, limited slots, shortened link, ₹750
> "registration fee" to a personal UPI handle. By the time the placement cell
> denies it, the money is gone.
>
> HERD is an immune system for that. *(paste screenshot)* Verdict, in under a
> second, offline, no model call — that's Tier 0, and it cost nothing. Every row
> in this panel cites a rule or a source; there's no opinion anywhere in it.
>
> Now the interesting part. *(paste a mutated version)* Different company,
> different amount, different link — same **strain**. HERD recognises the
> template, not the message, so this came back instantly from memory. And
> because strain memory is shared across colleges, the second campus to see this
> operation is already immune.
>
> Here's a **genuine** notice. *(paste)* UNVERIFIED — not TRUE. It won't confirm
> anything without a source entitled to confirm it, because "nothing looks
> wrong" is exactly what a good scam looks like too. On our labelled set it has
> never once accused a real notice.
>
> And — *(unplug the wifi)* — again. Everything that needs the network says so,
> and the answer still arrives.
>
> The label is never the model's opinion. It's arithmetic over cited evidence.
> The LLM only writes the explanation, afterwards, for a decision it didn't
> make.

---

## 11. Pre-demo checklist

- [ ] `venv\Scripts\python.exe -m pytest tests\ -q` → all green
- [ ] `venv\Scripts\python.exe tools\eval_tier0.py --with-tier1` → **HARMFUL: 0**
- [ ] Run the whole demo once with the network **actually disconnected**
- [ ] Switch `HERD_INSTITUTION` to a second college and re-run — no code change
- [ ] Screenshots pre-loaded and pasteable without typing
- [ ] Know your three numbers cold: **13/13 caught, 0/14 accused, 0.214 margin**
- [ ] Be ready to say what is *not* built (§8) before a judge finds it
