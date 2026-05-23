"""FastAPI application for CS chatbot."""
import asyncio
import json
import logging
import pathlib
import time
from collections import defaultdict
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from backend.config import Config
from backend.rag_chain import RAGChain
from backend.conversation_store import ConversationStore
from backend.feedback_store import FeedbackStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-IP sliding-window rate limiter (in-memory, single-process)
# ---------------------------------------------------------------------------
_rate_windows: dict = defaultdict(list)
_ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str, max_requests: int, window_seconds: int = 60) -> bool:
    now = time.monotonic()
    cutoff = now - window_seconds
    _rate_windows[ip] = [t for t in _rate_windows[ip] if t > cutoff]
    if len(_rate_windows[ip]) >= max_requests:
        return False
    _rate_windows[ip].append(now)
    # Prevent the dict from growing indefinitely on long-running servers
    if len(_rate_windows) > 200_000:
        _rate_windows.clear()
    return True

app = FastAPI(title="CS Agent Chatbot API", version="1.0.0")

# Narrow CORS to the Vercel frontend in production; fall back to wildcard in dev
_allowed_origins = (
    ["http://localhost:3000", Config.FRONTEND_URL]
    if Config.FRONTEND_URL
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_rag_chain: Optional[RAGChain] = None
conversation_store = ConversationStore(max_conversations=Config.MAX_CONVERSATIONS)
feedback_store = FeedbackStore()


def get_rag_chain() -> RAGChain:
    """Lazily build RAG so / and /health work without OPENAI_API_KEY."""
    global _rag_chain
    if _rag_chain is not None:
        return _rag_chain
    if not (Config.OPENAI_API_KEY or "").strip():
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat is unavailable: OPENAI_API_KEY is not set. "
                "Add it to your environment or a .env file in the project root."
            ),
        )
    try:
        _rag_chain = RAGChain()
    except Exception as e:
        logger.error("RAG chain initialization failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Chat service is temporarily unavailable. Please try again later.",
        ) from e
    return _rag_chain


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    question: str
    conversation_id: Optional[str] = None  # For future conversation tracking


class Source(BaseModel):
    """Source information model."""
    source: str
    relevance_score: float
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    answer: str
    sources: List[Source]
    context_used: bool
    conversation_id: str


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "CS Agent Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/api/chat",
            "chat_stream": "/api/chat/stream",
            "feedback": "/api/feedback",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "chat_available": bool((Config.OPENAI_API_KEY or "").strip()),
    }


class FeedbackRequest(BaseModel):
    """Request model for feedback endpoint."""
    conversation_id: str
    turn_index: int
    helpful: bool


@app.post("/api/feedback")
async def feedback(request: FeedbackRequest, req: Request):
    """Record thumbs up/down for an assistant turn. Used for tuning and analytics."""
    ip = _client_ip(req)
    if not _check_rate_limit(ip, Config.RATE_LIMIT_FEEDBACK_RPM):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    feedback_store.add(
        conversation_id=request.conversation_id,
        turn_index=request.turn_index,
        helpful=request.helpful,
    )
    return {"ok": True}


@app.post("/api/feedback/general")
async def general_feedback(
    request: Request,
    message: str = Form(""),
    screenshot: Optional[UploadFile] = File(None),
):
    """Forward feedback from the Feedback modal to Slack (text webhook and/or file upload)."""
    ip = _client_ip(request)
    if not _check_rate_limit(ip, Config.RATE_LIMIT_FEEDBACK_RPM):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    text = (message or "").strip()
    if len(text) > Config.MAX_FEEDBACK_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message must be at most {Config.MAX_FEEDBACK_LENGTH} characters.",
        )

    payload: Optional[bytes] = None
    filename: Optional[str] = None
    if screenshot is not None and (screenshot.filename or "").strip():
        content_type = (screenshot.content_type or "").lower().split(";")[0].strip()
        if content_type not in _ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only image files (PNG, JPEG, GIF, WebP) are accepted.",
            )
        payload = await screenshot.read()
        if len(payload) > Config.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Screenshot must be under {Config.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
            )
        filename = screenshot.filename

    if payload:
        if not (Config.SLACK_BOT_TOKEN or "").strip() or not (
            Config.SLACK_FEEDBACK_CHANNEL_ID or ""
        ).strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Screenshot uploads require SLACK_BOT_TOKEN and "
                    "SLACK_FEEDBACK_CHANNEL_ID to be configured"
                ),
            )
        if not text:
            text = ""
        feedback_store.send_general_feedback_with_screenshot(text, payload, filename or "screenshot.png")
        return {"ok": True}

    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    feedback_store.send_general_feedback(text)
    return {"ok": True}


def _validate_question_length(question: str) -> None:
    """Raise 400 if question exceeds max length."""
    q = (question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    limit = Config.MAX_QUESTION_LENGTH
    if len(q) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"Question must be at most {limit} characters (got {len(q)}).",
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Chat endpoint - processes user questions and returns answers.

    Uses conversation_id to load prior turns and pass them to the LLM for
    coherent follow-up answers. Creates a new conversation_id when none is sent.
    """
    ip = _client_ip(req)
    if not _check_rate_limit(ip, Config.RATE_LIMIT_CHAT_RPM):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    _validate_question_length(request.question)

    conversation_id = request.conversation_id or conversation_store.create_id()
    history = conversation_store.get_recent_messages(conversation_id, last_n_turns=5)
    rag = get_rag_chain()

    try:
        result = await asyncio.wait_for(
            rag.query(
                request.question, conversation_history=history if history else None
            ),
            timeout=Config.CHAT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {Config.CHAT_TIMEOUT_SECONDS:.0f} seconds.",
        )
    except Exception as e:
        logger.error("Chat query failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error processing your question. Please try again."
        )

    conversation_store.add_message(conversation_id, "user", request.question)
    conversation_store.add_message(conversation_id, "assistant", result["answer"])
    sources = [
        Source(
            source=s["source"],
            relevance_score=s["relevance_score"],
            snippet=s.get("snippet"),
        )
        for s in result["sources"]
    ]
    return ChatResponse(
        answer=result["answer"],
        sources=sources,
        context_used=result["context_used"],
        conversation_id=conversation_id,
    )


def _sse_line(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Stream the assistant reply as SSE. Same request body as /api/chat."""
    ip = _client_ip(req)
    if not _check_rate_limit(ip, Config.RATE_LIMIT_CHAT_RPM):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    _validate_question_length(request.question)

    conversation_id = request.conversation_id or conversation_store.create_id()
    history = conversation_store.get_recent_messages(conversation_id, last_n_turns=5)
    rag_chain = get_rag_chain()
    accumulated = ""
    chunk_timeout = Config.STREAM_CHUNK_TIMEOUT_SECONDS
    total_timeout = Config.STREAM_TOTAL_TIMEOUT_SECONDS

    async def event_stream():
        nonlocal accumulated
        stream = rag_chain.query_stream(
            request.question, conversation_history=history if history else None
        )
        start = time.monotonic()
        try:
            while True:
                if time.monotonic() - start > total_timeout:
                    yield _sse_line(
                        {"event": "error", "message": f"Stream timed out after {total_timeout:.0f} seconds."}
                    )
                    break
                try:
                    event = await asyncio.wait_for(
                        stream.__anext__(), timeout=chunk_timeout
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    yield _sse_line(
                        {"event": "error", "message": f"No data received within {chunk_timeout:.0f} seconds."}
                    )
                    break

                if event["type"] == "start":
                    if event.get("message"):
                        accumulated = event["message"]
                    yield _sse_line(
                        {
                            "event": "start",
                            "sources": event.get("sources", []),
                            "context_used": event.get("context_used", False),
                            "conversation_id": conversation_id,
                            **({"message": event["message"]} if event.get("message") else {}),
                        }
                    )
                elif event["type"] == "token":
                    accumulated += event["delta"]
                    yield _sse_line({"event": "token", "delta": event["delta"]})
                elif event["type"] == "done":
                    conversation_store.add_message(conversation_id, "user", request.question)
                    conversation_store.add_message(conversation_id, "assistant", accumulated)
                    yield _sse_line({"event": "done"})
        except Exception as e:
            logger.error("SSE stream error: %s", e, exc_info=True)
            yield _sse_line({"event": "error", "message": "An unexpected error occurred. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    from backend.config import Config

    # Reload only backend package changes — avoids restarting when tooling edits
    # `.cursor/` or frontend files while the repo root is watched.
    _reload_root = pathlib.Path(__file__).resolve().parent

    uvicorn.run(
        "backend.main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True,
        reload_dirs=[str(_reload_root)],
    )
