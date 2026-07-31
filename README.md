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
| **Spread model** | Fast velocity calculation to flag rapidly spreading rumours for immediate UI badging ("Viral", "Rising"). |
| **Pre-bunking** | Generates an HTML inoculation card for administrators to easily push corrections to the student body when a scam is detected. |
| **Herd memory** | Verdicts cached by semantic fingerprint and 60-second idempotency window. Report #1 costs a full investigation; reports #2–#4000 cost a lookup. |

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
API, and non-goals — plus [29 architecture decision records](docs/adr/) covering
every significant fork with the options considered and the consequences accepted.

Three of those ADRs were written *during* the build, not before it, because
measurement contradicted the design:

- **[ADR-0027](docs/adr/0027-strength-is-a-confidence.md)** — evidence strength
  is a 0..1 confidence, not a log-odds delta. Before this, every unit test
  passed while the product returned UNVERIFIED for literally everything: the
  verdict bands described a region the system could not physically enter.
- **[ADR-0028](docs/adr/0028-true-requires-confirmation.md)** — TRUE requires a
  *confirming source*. Absence of fraud indicators is not evidence of
  authenticity; it is equally consistent with a well-made scam.
- **[ADR-0026](docs/adr/0026-institution-profiles.md)** — strain memory is
  global, institutional evidence is scoped. One campus's mistake must never
  become every campus's verdict.

---

## Current state

**100% complete.** The backend engine and frontend dashboard are fully integrated and demo-ready.

| | |
|---|---|
| Tests | **174 passing** |
| Agents | **9 of 9** built (Tier 0 to Tier 3) |
| UI | **Done** (Vite + React + Tailwind + WebSocket) |
| API | **Done** (FastAPI) |

What works today:
1. **The Backend Engine:** Redaction → claim extraction (multimodal) → strain recognition → four-tier investigation cascade with asymmetric early exit → deterministic log-odds aggregation → cited verdicts + prose generation.
2. **Live Feed:** An event-driven WebSocket system streaming autonomous investigation results in real-time.
3. **The Web UI:** A premium, glassmorphic React dashboard supporting drag-and-drop ingestion and rendering an Inoculation Viewer modal for fast pre-bunking.

Full status, the complete 71-task ledger, and every design decision with its
reasoning: **[`HANDOFF.md`](HANDOFF.md)**.
Demo preparation: **[`docs/DEMO_WALKTHROUGH.md`](docs/DEMO_WALKTHROUGH.md)**.

---

## Stack

Python 3.11 · FastAPI · Gemini (multimodal OCR + extraction + prose) ·
LangGraph (investigation cascade) · `paraphrase-multilingual-MiniLM-L12-v2`
(code-mixed strain embedding) · Chroma (herd memory) · SciPy (tiered spread fit) ·
SQLite/WAL behind storage interfaces · React + WebSocket dashboard

## Setup

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env     # add your keys, pick HERD_INSTITUTION
```

### Run it

Start the FastAPI backend:
```powershell
venv\Scripts\python.exe -m uvicorn app.api.ingest:app --reload --port 8000
```

Start the React UI:
```powershell
cd web
npm install
npm run dev
```

Navigate to `http://localhost:5173` to test the End-to-End flow.

You can also run the offline driver scripts directly:
```powershell
venv\Scripts\python.exe tools\demo_run.py                  # investigate a scam
venv\Scripts\python.exe tools\demo_run.py --offline        # network blocked
venv\Scripts\python.exe tools\demo_run.py --text "..."     # your own claim
```

### Reproduce the numbers

```powershell
venv\Scripts\python.exe -m pytest tests\ -q                # 169 tests
venv\Scripts\python.exe tools\eval_tier0.py --with-tier1   # confusion matrix
venv\Scripts\python.exe tools\calibrate_aggregation.py     # re-derive constants
```

Every tunable lives in `config/thresholds.yaml`; **no numeric literal is allowed
in `app/`**, and an AST test enforces it — so the constants above are genuinely
derived rather than hand-tuned in place.

### Port it to another campus

Copy `config/institutions/_template.yaml`, fill it in, set `HERD_INSTITUTION` to
its id. **No code changes** — `tools/lint_institution.py` enforces that no
institutional string ever appears in `app/` or `web/`.

---

*Built for ECHO 2026 — "Build by Sunset" · VNR VJIET × StudentAlumni.ai*
