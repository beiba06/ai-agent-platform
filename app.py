"""Web layer: serves the chat page, takes uploads, and streams answers as Server-Sent Events."""
import asyncio
import json
from contextlib import aclosing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, Field

import agent
import rag

STATIC = Path(__file__).parent / "static"
CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
MAX_UPLOAD = 5 * 1024 * 1024
SAMPLE = rag.read("sample.pdf", (STATIC / "sample.pdf").read_bytes())  # parsed once: slow on a small server

app = FastAPI()


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Content-Security-Policy": CSP})


@app.get("/sample.pdf")
def sample():
    return FileResponse(STATIC / "sample.pdf")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat", response_class=EventSourceResponse)
async def chat(req: ChatRequest):
    async with aclosing(agent.chat(req.session_id, req.message)) as events:
        async for event in events:
            if event["type"] in ("done", "error"):  # one log line per answer, without message text or sources
                print(json.dumps({k: v for k, v in event.items() if k != "sources"}), flush=True)
            yield event


@app.post("/sample")
async def load_sample(session_id: str = Query(min_length=8, max_length=64)):
    agent.open_chat(session_id)
    rag.add(session_id, SAMPLE)
    return {"message": "sample.pdf is ready. Ask a question about it."}


@app.post("/upload")
async def upload(request: Request, session_id: str = Query(min_length=8, max_length=64),
                 name: str = Query(min_length=1, max_length=200)):
    if not name.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Please upload a PDF, TXT or MD file.")
    data = bytearray()
    async for chunk in request.stream():  # stop reading as soon as the limit is passed
        data += chunk
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "That file is larger than 5 MB.")
    try:
        passages = await asyncio.to_thread(rag.read, name, data)  # parsing is slow: keep the server responsive
    except Exception:
        raise HTTPException(400, "That file could not be read.") from None
    if not passages:
        raise HTTPException(400, "No text found in that file. Scanned PDFs are not supported.")
    agent.open_chat(session_id)
    rag.add(session_id, passages[:rag.MAX_PASSAGES])
    note = " Only the first part of it was indexed." if len(passages) > rag.MAX_PASSAGES else ""
    return {"message": f"{name} is ready. Ask a question about it.{note}"}
