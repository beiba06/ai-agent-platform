# AI Agent Platform

A multi-tool AI agent that breaks down complex tasks into tool calls, retrieves context via RAG, and streams structured responses.

## Architecture (MVP)

```
Client (WebSocket) → FastAPI
                        └── Agent (LangGraph)
                              ├── tool: web_search (Tavily)
                              ├── tool: rag_query (ChromaDB)
                              └── tool: code_exec (subprocess)
                        └── Memory (Redis)
```

**Core principle: minimum code, maximum impact.** No abstractions until needed. One file per concern. No config framework, no ORM, no middleware stack.

## MVP Milestones

1. **M1: Agent core** — FastAPI + LangGraph agent + 1 tool (web search) → chat works
2. **M2: RAG** — Upload docs + query them via ChromaDB → agent answers from your docs
3. **M3: Code exec** — Agent can run Python code in a sandbox → agent solves code tasks
4. **M4: Memory** — Redis conversation history → multi-turn conversations
5. **M5: Streaming** — WebSocket token streaming → real-time UX
6. **M6: Deploy** — Docker Compose + Railway → live URL

## File Structure (MVP — 8 files total)

```
ai-agent-platform/
├── app.py              # FastAPI: routes + WebSocket (< 80 lines)
├── agent.py            # LangGraph agent graph (< 100 lines)
├── tools.py            # Tool definitions: search, rag, code (< 80 lines)
├── rag.py              # ChromaDB: ingest + query (< 60 lines)
├── requirements.txt    # Dependencies
├── Dockerfile          # Single-stage Python container
├── docker-compose.yml  # App + Redis + ChromaDB
└── README.md
```

**That's it. 8 files. ~320 lines of code for a working AI agent with RAG.**

## Tech Choices (and why)

| Choice | Why | Not |
|--------|-----|-----|
| **FastAPI** | async, WebSocket native, zero boilerplate | Flask (no async), Django (too heavy) |
| **LangGraph** | stateful agent graph, tool calling built-in | Raw OpenAI (no orchestration), CrewAI (too abstract) |
| **ChromaDB** | embedded, zero config, pip install | Pinecone (needs account), Weaviate (needs server) |
| **Redis** | session memory, 1 line to connect | SQLite (no TTL), Postgres (overkill for memory) |
| **Tavily** | search API built for agents, free tier | SerpAPI (expensive), Google (complex auth) |

## Running Locally

```bash
pip install -r requirements.txt
docker compose up -d redis chromadb   # or skip if running without
uvicorn app:app --reload
```

## API

```
POST /chat          {"message": "...", "session_id": "..."}
POST /upload        multipart file upload → ingest into RAG
WS   /ws/{session}  streaming chat via WebSocket
GET  /health        health check
```
