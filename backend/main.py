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

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from knowledge_loader import KnowledgeBase
from llm_handler import LLMHandler
from document_loader import parse_document, SUPPORTED_EXTENSIONS

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


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    t0 = time.perf_counter()
    cid = body.conversationId
    logger.info("chat request cid=%r message=%r", cid, body.message[:80])

    # Last MAX_HISTORY_ENTRIES messages for context
    history = _conversation_store.get(cid, [])[-MAX_HISTORY_ENTRIES:]

    # Keyword search over the knowledge base
    kb_results = knowledge_base.search(body.message)
    logger.info("kb hits=%d for cid=%r", len(kb_results), cid)

    # Call Claude with a hard timeout
    try:
        response_text, confidence = await asyncio.wait_for(
            llm_handler.generate(
                user_message=body.message,
                kb_context=kb_results,
                history=history,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("LLM timeout after %.0fs for cid=%r", LLM_TIMEOUT_SECONDS, cid)
        raise HTTPException(
            status_code=504,
            detail=f"Ollama did not respond within {int(LLM_TIMEOUT_SECONDS)} seconds. Make sure Ollama is running and the model is pulled.",
        )
    except Exception as exc:
        logger.error("LLM error for cid=%r: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Could not reach Ollama. Make sure it is running: ollama serve",
        ) from exc

    # Persist the exchange, capped to avoid unbounded growth
    store = _conversation_store.setdefault(cid, [])
    store.extend([
        {"role": "user", "content": body.message},
        {"role": "assistant", "content": response_text},
    ])
    if len(store) > MAX_HISTORY_ENTRIES:
        _conversation_store[cid] = store[-MAX_HISTORY_ENTRIES:]

    sources = [r["section"] for r in kb_results[:3]]
    elapsed = time.perf_counter() - t0
    logger.info("chat ok cid=%r elapsed=%.2fs confidence=%.2f sources=%s", cid, elapsed, confidence, sources)

    return ChatResponse(
        message=response_text,
        sources=sources,
        confidence=round(confidence, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


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


@app.post("/api/feedback", response_model=FeedbackResponse, tags=["chat"])
@limiter.limit("30/minute")
async def feedback(request: Request, body: FeedbackRequest) -> FeedbackResponse:
    logger.info(
        "feedback cid=%r messageId=%r value=%r",
        body.conversationId,
        body.messageId,
        body.feedback,
    )
    # Production: persist to database (e.g. INSERT INTO feedback ...)
    return FeedbackResponse(status="recorded")
