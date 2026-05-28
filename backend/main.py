"""
HR Knowledge Copilot — FastAPI backend

Endpoints:
  GET  /health          — liveness check
  POST /api/chat        — primary chat (rate-limited, 10 req/min per IP, 120s timeout)
  POST /api/feedback    — thumbs-up/down signal from users
"""

import asyncio
import os
import time
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Literal

import json

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from knowledge_loader import KnowledgeBase
from llm_handler import LLMHandler
from document_loader import parse_document, SUPPORTED_EXTENSIONS
from database import init_db, save_exchange, save_feedback, get_conversations, get_conversation_messages, get_feedback_summary

# ── Logging ──────────────────────────────────────────────────────────────── #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("hr_copilot")

# ── Environment ──────────────────────────────────────────────────────────── #

load_dotenv()

KB_PATH = os.getenv("KB_PATH", "../data/knowledge_base.md")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]

LLM_TIMEOUT_SECONDS = 120.0  # Local models are slower than cloud APIs

# In-memory conversation history { conversationId: [{"role": ..., "content": ...}, ...] }
_conversation_store: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY_ENTRIES = 12  # 6 full exchanges

# ── Application setup ─────────────────────────────────────────────────────── #

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting HR Copilot — model=%s host=%s kb=%s cors_origins=%s timeout=%.0fs",
        OLLAMA_MODEL, OLLAMA_HOST, KB_PATH, CORS_ORIGINS, LLM_TIMEOUT_SECONDS,
    )
    logger.info("Make sure Ollama is running: ollama serve")
    init_db()
    yield
    logger.info("Shutting down HR Copilot")


app = FastAPI(
    title="HR Knowledge Copilot API",
    version="2.0.0",
    description="Enterprise HR Knowledge Base powered by local Ollama LLM",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Singletons ───────────────────────────────────────────────────────────── #

knowledge_base = KnowledgeBase(kb_path=KB_PATH)
llm_handler = LLMHandler(model=OLLAMA_MODEL, host=OLLAMA_HOST)

# ── Schemas ──────────────────────────────────────────────────────────────── #


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The employee's HR question",
    )
    conversationId: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Client-generated conversation identifier",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped

    @field_validator("conversationId")
    @classmethod
    def strip_conversation_id(cls, v: str) -> str:
        return v.strip()


class ChatResponse(BaseModel):
    message: str
    sources: list[str]
    confidence: float
    timestamp: str


class FeedbackRequest(BaseModel):
    messageId: str = Field(..., min_length=1, max_length=100)
    conversationId: str = Field(..., min_length=1, max_length=100)
    feedback: Literal["helpful", "not_helpful"]


class FeedbackResponse(BaseModel):
    status: str


class UploadResponse(BaseModel):
    filename: str
    sections_added: int
    total_kb_sections: int


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Exception handlers ───────────────────────────────────────────────────── #


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routes ───────────────────────────────────────────────────────────────── #


@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "kb_sections": knowledge_base.section_count,
        "model": OLLAMA_MODEL,
        "ollama_host": OLLAMA_HOST,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/chat", tags=["chat"])
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    cid = body.conversationId
    logger.info("chat request cid=%r message=%r", cid, body.message[:80])

    history = _conversation_store.get(cid, [])[-MAX_HISTORY_ENTRIES:]
    kb_results = knowledge_base.search(body.message)
    sources = [r["section"] for r in kb_results[:3]]
    confidence = llm_handler.estimate_confidence(kb_results)

    async def event_stream() -> AsyncGenerator[str, None]:
        full_text = ""
        try:
            async for chunk in llm_handler.stream(
                user_message=body.message,
                kb_context=kb_results,
                history=history,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            # Persist to in-memory history
            store = _conversation_store.setdefault(cid, [])
            store.extend([
                {"role": "user", "content": body.message},
                {"role": "assistant", "content": full_text},
            ])
            if len(store) > MAX_HISTORY_ENTRIES:
                _conversation_store[cid] = store[-MAX_HISTORY_ENTRIES:]

            # Persist to SQLite for audit
            save_exchange(cid, body.message, full_text, sources, confidence)

            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'confidence': round(confidence, 2), 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            logger.info("chat stream done cid=%r tokens=%d confidence=%.2f", cid, len(full_text), confidence)

        except Exception as exc:
            logger.error("LLM stream error cid=%r: %s", cid, exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not reach Ollama. Make sure it is running: ollama serve'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/upload", response_model=UploadResponse, tags=["documents"])
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    sections = parse_document(data, filename)
    if not sections:
        raise HTTPException(status_code=422, detail="Could not extract any content from the file")

    added = knowledge_base.add_sections(sections)
    logger.info("upload filename=%r sections_added=%d total=%d", filename, added, knowledge_base.section_count)
    return UploadResponse(
        filename=filename,
        sections_added=added,
        total_kb_sections=knowledge_base.section_count,
    )


@app.get("/api/audit/conversations", tags=["audit"])
async def audit_conversations(limit: int = 100) -> list[dict]:
    """Return all conversations with message counts and avg confidence — for HR audit."""
    return get_conversations(limit=limit)


@app.get("/api/audit/conversations/{conversation_id}", tags=["audit"])
async def audit_conversation_detail(conversation_id: str) -> list[dict]:
    """Return the full message transcript for a single conversation."""
    messages = get_conversation_messages(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@app.get("/api/audit/feedback", tags=["audit"])
async def audit_feedback() -> list[dict]:
    """Return aggregated helpful / not_helpful counts."""
    return get_feedback_summary()


@app.post("/api/feedback", response_model=FeedbackResponse, tags=["chat"])
@limiter.limit("30/minute")
async def feedback(request: Request, body: FeedbackRequest) -> FeedbackResponse:
    logger.info("feedback cid=%r messageId=%r value=%r", body.conversationId, body.messageId, body.feedback)
    save_feedback(body.messageId, body.conversationId, body.feedback)
    return FeedbackResponse(status="recorded")
