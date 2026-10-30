# AI Agent Platform

A small, framework-free AI agent. It answers questions by searching the web, reading documents you upload, and running code in a sandbox, then streams the answer back with citations.

## Architecture

```
Browser (static/index.html)
   │  POST /chat    → Server-Sent Events: text · tool calls · citations · cost
   │  POST /upload  → PDF / TXT / MD (raw bytes, max 5 MB)
   ▼
FastAPI (app.py)
   └── agent loop (agent.py) ──► Claude API (Anthropic Python SDK)
         │                          ├── web_search      server tool, runs at Anthropic
         │                          └── code_execution  server tool, sandboxed, no internet
         └── search_docs tool ──► rag.py ──► SQLite FTS5, one in-memory index per chat
```

**Core principle: minimum code, maximum impact.** One container, one secret, no framework, no extra services. Nothing the API already provides (search, code sandbox, citations) gets rebuilt.

## Milestones

- [x] **M1: Agent core**: `agent.py`, a streaming tool-use loop with web search and code execution. It answers current-events questions with cited sources.
- [x] **M2: Chat UI**: `app.py` + `static/index.html`. Answers stream into the browser, tool calls appear as they happen, follow-up questions keep context, and each answer shows its tokens, latency and cost.
- [x] **M3: Your documents**: `rag.py` + `/upload` + the `search_docs` tool. Answers cite the file and page. A sample document and two example prompts let visitors try it without uploading anything.
- [x] **M4: Measure**: `evals/` runs 20 questions, including a prompt-injection test, through the agent and through the same model with no tools, on Opus, Sonnet and Haiku. The README reports pass rate, latency and cost per answer, and these results pick the demo model.
- [ ] **M5: Ship**: `Dockerfile` + Render + a capped API workspace give a live URL. A demo GIF goes at the top of this README.

## Results

Measured on 20 labelled questions in [`evals/cases.jsonl`](evals/cases.jsonl): 8 about a document, 4 about events too recent for the model to know, 2 needing both, 2 follow-ups, 1 code task, a planted prompt injection, a question the document can't answer, and one simple question that should use no tools. One run per model on 2026-10-30, with effort set to low.

| Model | Agent | Same model, no tools | Avg time | Avg cost |
|---|---|---|---|---|
| `claude-haiku-5-5` | 19/20 | 10/20 | 5.9s | $0.007 |
| `claude-sonnet-5-5` | 20/20 | 9/20 | 5.8s | $0.039 |
| `claude-opus-5-5` | 20/20 | 10/20 | 8.0s | $0.080 |

- **What the tools add:** about 10 more correct answers. Without tools, every model missed all 4 recent-events questions.
- **Why Sonnet is the default:** it matched Opus at 20/20, at half the cost and a little faster.
- **Prompt injection:** all three models ignored the planted instruction and answered from the document.
- **What failed:** keyword search sometimes misses the page with the document's publication date (`both-date`). Haiku missed it in this run, and Sonnet missed it in an earlier one, so treat that case as unreliable rather than solved.
- **How far to trust this:** it's a small test, and grading is keyword matching, not a human reading each answer. Two patterns (`doc-risk`, `safety-unknown`) were corrected after a first run rejected right answers, then every model was rerun. The no-tools runs get no document, so their document passes come from what the model already knew about this public framework.

Run it with `MODEL=claude-haiku-5-5 .venv/bin/python evals/run.py`.

## File Structure

```
ai-agent-platform/
├── app.py              # FastAPI: page, /chat (SSE), /upload, /health           (70 lines)
├── agent.py            # Claude tool-use loop, tools, per-chat guards           (126 lines)
├── rag.py              # SQLite FTS5: split by page, index, search              (47 lines)
├── static/index.html   # chat UI: streaming text, tool lines, sources, upload   (143 lines)
├── static/sample.pdf   # NIST AI 100-1 (AI RMF 1.0), a US government publication
├── evals/              # run.py, cases.jsonl, injection.txt                     (61 lines)
├── requirements.txt    # anthropic, fastapi, uvicorn, pypdf (exact pins)
├── Dockerfile          # single-stage python:3.12-slim, non-root user
└── README.md
```

**About 250 lines of Python and one 143-line page: no database server, no vector DB, no Redis, no docker-compose.**

## Tech Choices (and why)

| Choice | Why | Not |
|--------|-----|-----|
| **Anthropic Python SDK, no framework** | the agent loop is ~30 lines; every step is visible and easy to explain | LangGraph / LangChain (extra layers around a single loop) |
| **Claude server tools: web search + code execution** | zero code, no second API key; code runs in Anthropic's sandbox with no internet, never on this server | Tavily (second key), `subprocess` (runs model-written code next to the API key) |
| **SQLite FTS5 (BM25 keyword search)** | built into Python: no extra packages, ~2 MB RAM; the agent writes its own search queries | ChromaDB + local embeddings (~1 GB RAM, ~600 MB image: too big for free hosting) |
| **In-memory sessions** | an append-only message list and its own search index per chat, no extra service; resets on restart, which is fine for a demo | Redis (another service to run) |
| **Server-Sent Events (FastAPI built-in)** | one endpoint; keepalive pings hold the connection open while the agent searches | WebSocket (connection handling on both ends) |
| **FastAPI + one static HTML page** | async streaming, serves its own UI, no build step | React / Next.js (a second project) |
| **Render free tier (Docker)** | deploys from GitHub, fits in 512 MB | HF Spaces (Docker now needs PRO), Railway (30-day trial, then $1/mo credit), Fly.io / Koyeb (no free tier) |

## Safety & Cost

A public demo spends real API credit, so limits come first:

- **Spend and rate limits:** the API key belongs to a dedicated Anthropic Console workspace with a monthly spend limit (e.g. $20) and a requests-per-minute limit. When a limit is reached, the app shows "demo budget used up".
- **No code runs on the server:** code execution happens in Anthropic's sandbox. Every tool is read-only, and the page renders answers as plain text. Instructions injected through a web page or document therefore can't take actions, reach secrets, or inject HTML.
- **Visitor isolation:** each chat has its own in-memory search index, so visitors never see each other's files. A notice tells visitors that their files are sent to Anthropic's API.
- **Caps:** messages up to 4,000 characters; uploads up to 5 MB and 500 passages, one file per chat; 20 questions per chat; at most 3 web searches and 8 model calls per answer; one answer at a time per chat; at most 100 chats in memory, oldest dropped first. Errors show a short message, never internals.
- **Known limits:** keyword search can miss paraphrases, and "summarize the whole file" only sees the best-matching passages. Scanned PDFs have no text to search. Request bodies on `/chat` aren't size-capped before validation, so a huge request could crash a free instance until it restarts.
- **Model:** set by the `MODEL` env var, default `claude-sonnet-5-5`. Measured cost per question: about $0.04 on Sonnet 5.5, $0.08 on `claude-opus-5-5` and $0.007 on `claude-haiku-5-5` (see Results).

## Running Locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # optional: export MODEL=claude-haiku-5-5
.venv/bin/uvicorn app:app --reload        # then open http://localhost:8000
```

## API

```
GET  /                          chat page
GET  /sample.pdf                the sample document
POST /chat                      {"session_id": "...", "message": "..."} → SSE events (text, tool, citation, done, error)
POST /upload?session_id=&name=  raw file bytes (PDF / TXT / MD, max 5 MB) → indexed for that chat
GET  /health                    health check
```

## Deploy

**Render (free):** New → Web Service → connect this repo (Render builds the `Dockerfile`) → add `ANTHROPIC_API_KEY` → deploy. Free instances sleep after 15 minutes idle and take about a minute to wake.

**Alternative: Google Cloud Run.** It has faster cold starts and a generous free tier, but needs a billing account with a card. Deploy with `gcloud run deploy --source .` and set `--max-instances 1`.
