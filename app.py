"""Web layer: serves the chat page and streams the agent's answers as Server-Sent Events."""
import json
from contextlib import aclosing
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, Field

import agent

PAGE = Path(__file__).parent / "static" / "index.html"
CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

app = FastAPI()


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


@app.get("/")
def index():
    return FileResponse(PAGE, headers={"Content-Security-Policy": CSP})


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
