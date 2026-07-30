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
   +----------+-----------+
              | new strain
              v
   +----------------------------------------------+
   |        autonomous investigation swarm         |
   |  official source - careers page - domain age  |
   |  fraud heuristics - URL safety - provenance   |
   +------------------+---------------------------+
                      v
   +----------------------+
   |  evidence-cited      |
   |  verdict + confidence|
   +----------+-----------+
              v
   +----------------------+
   |  spread model (SEIR) |--> alert *before* the projected peak
   +----------+-----------+
              v
        pre-bunk push to those not yet reached
```

### Core components

| Component | What it does |
|---|---|
| **Ingestion** | Web upload + QR, Telegram bot, Android share-intent. Screenshot-first, because that's how forwards actually travel. |
| **Claim extraction** | Turns messy code-mixed text into a structured, falsifiable claim. |
| **Strain clustering** | Rumours *mutate* as they spread. Variants are grouped into one strain with a visible mutation tree. |
| **Investigation swarm** | Parallel specialist agents return **evidence, not opinions** — official sources, the company's real careers page, domain age/WHOIS, URL safety, fraud heuristics, poster provenance. |
| **Spread model** | SEIR fit over report timestamps → R₀, velocity, projected peak. Decides *when* to alert. |
| **Pre-bunking** | Pushes inoculation to people in the predicted path who haven't seen it yet. |
| **Herd memory** | Verdicts cached by semantic fingerprint. Report #1 costs a full investigation; reports #2–#4000 cost a lookup. |

---

## Why it compounds

Scams scale by repetition — the same template, resent forever. HERD turns that
strength into a weakness:

**The wider an attack spreads, the cheaper it becomes to neutralise.**

One student's investigation becomes permanent immunity for everyone who follows.

---

## Privacy

HERD is **report-driven and consent-based**. It never reads a group, never joins
a chat, and never monitors anyone. It only ever sees what a human explicitly
hands it — intercepting a habit that already exists, since people already forward
suspicious messages to a friend asking *"is this real?"*

---

## Stack

Python · FastAPI · Gemini (multimodal OCR + extraction + synthesis) ·
LangGraph (investigation swarm) · sentence-transformers + HDBSCAN (strain
clustering) · Chroma (herd memory) · SciPy (SEIR fit) · Redis Streams ·
React + WebSocket dashboard

## Setup

```bash
cp .env.example .env     # add your keys
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

*Built for ECHO 2026 — "Build by Sunset" · VNR VJIET × StudentAlumni.ai*
