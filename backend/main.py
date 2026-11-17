import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from answer import NOT_FOUND, answer, answer_stream, is_relevant, retrieve, to_sources

# Comma-separated list, e.g. "https://my-app.vercel.app,http://localhost:3000"
ALLOWED_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskBody(BaseModel):
    question: str


def sse(event, data):
    # One Server-Sent Event; data is JSON so newlines in the answer stay safe
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(body: AskBody):
    text, chunks = answer(body.question)
    return {"answer": text, "sources": to_sources(chunks)}


@app.post("/ask/stream")
def ask_stream(body: AskBody):
    chunks = retrieve(body.question)

    def events():
        if not is_relevant(chunks):
            yield sse("sources", [])
            yield sse("token", NOT_FOUND)
            yield sse("done", {})
            return

        yield sse("sources", to_sources(chunks))
        try:
            for text in answer_stream(body.question, chunks):
                yield sse("token", text)
        except Exception as e:
            yield sse("error", f"The model failed to answer: {e}")
        yield sse("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
