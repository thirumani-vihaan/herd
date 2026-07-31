# HERD

**An immune system for campus misinformation.**

🚀 **Live Deployment:** [https://herd-backend-ofrf.onrender.com](https://herd-backend-ofrf.onrender.com)

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

Everything below is measured on this repository, not estimated.

| | |
|---|---|
| Tests | **198 passing** (`pytest tests/ -q`, ~35s) |
| Agents | **9 of 9** returning evidence across Tiers 0–3 |
| Wiring check | **9 of 9 alive** (`tools/check_wiring.py` invokes every agent) |
| Corpus accuracy | **38% exact label**, **13 of 18** scams caught as FALSE, **0** genuine notices libelled |
| Warm investigation | **~1.2 s** end to end, all four tiers |
| API | FastAPI, returns the full trace inline |
| UI | Vite + React + Tailwind, renders the whole judgement |

What works today:

1. **The engine.** Redaction → claim extraction (multimodal) → strain
   recognition → four-tier cascade with asymmetric early exit → deterministic
   log-odds aggregation → cited verdict. The label is arithmetic; the LLM only
   writes the prose, and the system runs without it.
2. **Real memory.** Reports, claims and strains are persisted. The second
   report of the same rumour is recognised as the same strain, and velocity is
   computed from stored timestamps — never projected from a flag.
3. **The dashboard.** Every agent that looked at the message, what it found,
   what it cited, and the exact path belief took through the tiers — including
   the tiers that never had to be bought.

Full status, the task ledger, and every design decision with its reasoning:
**[`HANDOFF.md`](HANDOFF.md)**.
Demo preparation: **[`docs/DEMO_WALKTHROUGH.md`](docs/DEMO_WALKTHROUGH.md)**.

---

## Stack

Python 3.11 · FastAPI · **Featherless.ai** (open-source LLM inference via Qwen for
verdict prose synthesis) · Gemini (multimodal OCR + claim extraction + embeddings) ·
LangGraph (investigation cascade) · Gemini Embeddings
(code-mixed strain embedding) · Chroma (herd memory) · SciPy (tiered spread fit) ·
SQLite/WAL behind storage interfaces · React + Vite + Tailwind dashboard

### Multi-provider AI architecture

HERD deliberately separates AI concerns across providers:

| Provider | Role | Why |
|---|---|---|
| **Featherless.ai** | Verdict prose synthesis | Open-source model (Qwen2.5) writes transparent, auditable explanations. The verdict label is deterministic — not LLM-dependent — so prose is a presentation layer, and using an open model makes it inspectable. |
| **Gemini** | Claim extraction + embeddings | Multimodal OCR for screenshot-first ingestion. Gemini embeddings for strain recognition across code-mixed languages. |
| **Deterministic** | Verdict computation | Log-odds aggregation produces the label arithmetically. No LLM ever decides truth. |

---

## Setup

### Prerequisites

| | |
|---|---|
| Python | **3.11** (3.12+ is not supported by the pinned wheels) |
| Node.js | **18+** (for the dashboard only) |
| Disk | ~500 MB — the multilingual embedding model downloads on first run |

### 1. Clone and install the backend

```powershell
git clone https://github.com/thirumani-vihaan/hackathon.git herd
cd herd

python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux the interpreter is `venv/bin/python` — every command below
works identically with that path substituted.

### 2. Configure

```powershell
copy .env.example .env
```

Then open `.env`. Only one value is genuinely required:

| Key | Required? | What happens without it |
|---|---|---|
| `REPORTER_HASH_SALT` | **yes** | Set it to any random string. It is the salt for pseudonymous reporter hashing. |
| `HERD_INSTITUTION` | pre-filled | Must match a filename stem in `config/institutions/`. |
| `GEMINI_API_KEY` | optional | Claim extraction falls back to a deterministic parser and the summary is written from the evidence itself. **Verdicts are unaffected** — no verdict is ever produced by a language model. |
| `FEATHERLESS_API_KEY` | **recommended** | Powers the verdict prose synthesis via Featherless.ai (Qwen2.5). Without it, prose falls back to Gemini, then to a deterministic summary. |
| `GOOGLE_SAFE_BROWSING_API_KEY` | optional | The URL-safety agent reports `unavailable` instead of checking the blocklist. Every other agent still runs. |
| `TELEGRAM_BOT_TOKEN` | optional | The Telegram ingestion path is disabled. The web path is unaffected. |

Missing optional keys never break an investigation. An agent that cannot do its
job says so, in the open, in the evidence ledger — it does not guess.

### 3. Run the backend

```powershell
venv\Scripts\python.exe -m uvicorn app.api.ingest:app --port 8000
```

The **first** start downloads the embedding model and takes a minute or two.
Wait for `Application startup complete.` before sending anything — the model is
warmed during startup precisely so that the first real investigation is fast.

### 4. Run the dashboard

In a second terminal:

```powershell
cd web
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/ingest` to the backend on port
8000, so no CORS or extra configuration is needed. Paste a message, or click one
of the three built-in samples, and press **Run the investigation**.

### Without a browser

```powershell
venv\Scripts\python.exe tools\demo_run.py                  # investigate a scam
venv\Scripts\python.exe tools\demo_run.py --offline        # network blocked
venv\Scripts\python.exe tools\demo_run.py --text "..."     # your own claim
```

### Verify the install

```powershell
venv\Scripts\python.exe -m pytest tests\ -q                # 198 tests
venv\Scripts\python.exe tools\check_wiring.py              # every agent, invoked
```

`check_wiring.py` calls all nine agents for real and fails if any of them
degrades for a reason that is not a missing network dependency. It exists
because a broad `except` in each agent means a contract violation would
otherwise be silently swallowed — the suite once ran green over two dead tiers.

### Reproduce the numbers

```powershell
venv\Scripts\python.exe tools\eval_tier0.py --with-tier1   # confusion matrix
venv\Scripts\python.exe tools\calibrate_aggregation.py     # re-derive constants
```

Every tunable lives in `config/thresholds.yaml`; **no numeric literal is allowed
in `app/`**, and an AST test enforces it — so the constants above are genuinely
derived rather than hand-tuned in place.

### Troubleshooting

| Symptom | Cause |
|---|---|
| `error while attempting to bind ... 8000` | A previous backend is still running. Stop it, or pass `--port 8001` and update `web/vite.config.ts`. |
| Dashboard shows *could not investigate* | The backend is not up yet, or is still downloading the model on first run. |
| `OpenWebResearch — unavailable` in the ledger | Expected without a Gemini key or when rate-limited. It is the terminal tier; the verdict does not depend on it. |
| Install fails on `tokenizers` / `numpy` | You are not on Python 3.11. Check `venv\Scripts\python.exe --version`. |

### Port it to another campus

Copy `config/institutions/_template.yaml`, fill it in, set `HERD_INSTITUTION` to
its id. **No code changes** — `tools/lint_institution.py` enforces that no
institutional string ever appears in `app/` or `web/`.

---

*Built for ECHO 2026 — "Build by Sunset" · VNR VJIET × StudentAlumni.ai*
