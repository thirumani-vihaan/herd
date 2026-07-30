# HERD

**An immune system for campus misinformation.**

A message lands in the class group: *"Amazon off-campus drive for 2026 batch —
register here, limited slots."* It has a logo. It has a deadline. Forty people
forward it before anyone checks. Some register. Some pay the ₹750 "registration
fee." Three days later someone finally says *"guys, this is fake."*

Too late. The same thing happens every week — exams postponed, fest cancelled,
fee deadline extended, this company is hiring.

**The rumour always beats the correction.**

---

## The idea

HERD treats a rumour as an **infection, not a document**.

"Is this true?" is the easy question, and it always arrives too late — because the
person who bothers to check was never the one at risk. The people who get hurt are
the ones who never doubted it.

So the useful question is:

> **How fast is this spreading, who hasn't been reached yet, and can I get there first?**

That is an *interception* problem, not a classification problem. Epidemiology,
not fact-checking.

---

## How it works

```
   forward a suspicious message
              |
              v
   +----------------------+
   |  OCR + claim extract |   screenshots, code-mixed Telugu/Hindi/English
   +----------+-----------+
              v
   +----------------------+
   |  strain matching     |---- already known? --> instant verdict (cache hit)
   +----------+-----------+          (here or at any other institution)
              | new strain
              v
   +----------------------------------------------+
   |     autonomous investigation cascade          |
   |  T0 memory - T1 cheap deterministic checks    |
   |  T2 targeted agents - T3 full synthesis       |
   |  exits early, asymmetrically, when it can     |
   +------------------+---------------------------+
                      v
   +----------------------+
   |  evidence-cited      |
   |  verdict + confidence|
   +----------+-----------+
              v
   +----------------------+
   |  spread model        |--> alert *before* the projected peak
   |  (tiered by sample n)|    on expected harm, not a threshold
   +----------+-----------+
              v
        pre-bunk push to those not yet reached
```

### Core components

| Component | What it does |
|---|---|
| **Ingestion** | Web upload + QR, Telegram bot, Android share-intent. Screenshot-first, because that's how forwards actually travel. |
| **Claim extraction** | Turns messy code-mixed text into a structured, falsifiable claim. |
| **Strain clustering** | Rumours *mutate* as they spread. Variants are grouped into one strain with a visible mutation tree — incrementally, so a strain's identity never changes under it. |
| **Investigation cascade** | Four tiers, cheapest first, with asymmetric early exit. Specialist agents return **evidence, not opinions** — official sources, the company's real careers page, domain age, URL safety, payment heuristics. The label is set by deterministic log-odds aggregation; the LLM only writes the prose. |
| **Spread model** | Fits what the sample size can actually support — nothing under n=5, a Bayesian growth estimate to n=20, logistic beyond, full SEIR-Hawkes only past n=60. Everything is reported as an interval. |
| **Pre-bunking** | Pushes inoculation to people in the predicted path who haven't seen it yet, when projected harm prevented exceeds projected harm caused. |
| **Herd memory** | Verdicts cached by semantic fingerprint. Report #1 costs a full investigation; reports #2–#4000 cost a lookup. |

---

## Why it compounds

Scams scale by repetition — the same template, resent forever. HERD turns that
strength into a weakness:

**The wider an attack spreads, the cheaper it becomes to neutralise.**

One student's investigation becomes permanent immunity for everyone who follows.

And that immunity does not stop at the campus boundary. Strain memory is
**global**; institutional evidence is **scoped**. A scam template that cost one
campus a full investigation is recognised instantly at the next one — while that
campus's verdict is still derived from its own notice board, its own official
channels, its own evidence. Share the pattern, scope the proof.

The usual cold-start problem inverts: HERD is *most* valuable to the newest
institution, because it arrives carrying everyone else's accumulated immunity.

Nothing institution-specific lives in code. A new campus is one YAML file in
[`config/institutions/`](config/institutions/README.md).

---

## Privacy

HERD is **report-driven and consent-based**. It never reads a group, never joins
a chat, and never monitors anyone. It only ever sees what a human explicitly
hands it — intercepting a habit that already exists, since people already forward
suspicious messages to a friend asking *"is this real?"*

---

## Design

Full design documentation lives in [`docs/`](docs/) — architecture, data model,
investigation cascade, spread model, intervention, trust & safety, evaluation,
API, and non-goals — plus [27 architecture decision records](docs/adr/) covering
every significant fork with the options considered and the consequences accepted.

## Stack

Python · FastAPI · Gemini (multimodal OCR + extraction + prose) ·
LangGraph (investigation cascade) · `paraphrase-multilingual-MiniLM-L12-v2`
(code-mixed strain embedding) · Chroma (herd memory) · SciPy (tiered spread fit) ·
SQLite/WAL behind storage interfaces · React + WebSocket dashboard

## Setup

```bash
cp .env.example .env     # add your keys, pick HERD_INSTITUTION
pip install -r requirements.txt
uvicorn app.main:app --reload
```

To run against a different campus, copy
`config/institutions/_template.yaml`, fill it in, and set `HERD_INSTITUTION` to
its id. No code changes.

---

*Built for ECHO 2026 — "Build by Sunset" · VNR VJIET × StudentAlumni.ai*
