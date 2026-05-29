"""
HR Onboarding Copilot — FastAPI backend

Endpoints:
  GET  /health                                  — liveness check
  POST /api/chat                                — primary chat (case-aware, streaming)
  POST /api/feedback                            — thumbs-up/down signal
  POST /api/upload                              — document upload to KB
  POST /api/cases                               — create onboarding case
  GET  /api/cases/{case_id}                     — get case + workflow progress
  POST /api/cases/{case_id}/complete-item       — mark a checklist item done
  POST /api/cases/{case_id}/advance-stage       — move case to next stage
  POST /api/cases/{case_id}/escalate            — raise escalation to HR
  GET  /api/admin/cases                         — list all cases (HR admin)
  GET  /api/audit/conversations                 — conversation audit
  GET  /api/audit/conversations/{id}            — single conversation
  GET  /api/audit/feedback                      — feedback summary
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
from case_manager import (
    create_case, get_case, get_all_cases,
    complete_item, advance_stage, create_escalation,
    build_case_context,
)

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

LLM_TIMEOUT_SECONDS = 120.0

_conversation_store: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY_ENTRIES = 12  # 6 full exchanges

# ── App setup ────────────────────────────────────────────────────────────── #

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting HR Onboarding Copilot — model=%s host=%s kb=%s",
        OLLAMA_MODEL, OLLAMA_HOST, KB_PATH,
    )
    init_db()
    yield
    logger.info("Shutting down HR Onboarding Copilot")


app = FastAPI(
    title="HR Onboarding Copilot API",
    version="3.0.0",
    description="AI-powered HR Onboarding with workflow orchestration, session memory, case IDs, and human escalation",
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

knowledge_base = KnowledgeBase(kb_path=KB_PATH)
llm_handler = LLMHandler(model=OLLAMA_MODEL, host=OLLAMA_HOST)

# ── Schemas ──────────────────────────────────────────────────────────────── #


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversationId: str = Field(..., min_length=1, max_length=100)
    caseId: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped

    @field_validator("conversationId")
    @classmethod
    def strip_cid(cls, v: str) -> str:
        return v.strip()


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


class CreateCaseRequest(BaseModel):
    employee_name: str = Field(..., min_length=1, max_length=200)
    employee_email: str = Field(..., min_length=3, max_length=200)
    employee_id: str = Field(default="", max_length=100)
    department: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    manager_name: str = Field(default="", max_length=200)
    start_date: str = Field(default="", max_length=50)

    @field_validator("employee_name", "employee_email")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()


class CompleteItemRequest(BaseModel):
    stage_id: str = Field(..., min_length=1, max_length=100)
    item_id: str = Field(..., min_length=1, max_length=100)


class EscalateRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)
    escalated_by: str = Field(default="employee", max_length=50)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Exception handler ─────────────────────────────────────────────────────── #


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Health ────────────────────────────────────────────────────────────────── #


@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "kb_sections": knowledge_base.section_count,
        "model": OLLAMA_MODEL,
        "ollama_host": OLLAMA_HOST,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Chat ──────────────────────────────────────────────────────────────────── #


@app.post("/api/chat", tags=["chat"])
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    cid = body.conversationId
    logger.info("chat cid=%r case=%r message=%r", cid, body.caseId, body.message[:80])

    # Load case context if caseId provided
    case_context_str: str | None = None
    if body.caseId:
        case = get_case(body.caseId)
        if case:
            case_context_str = build_case_context(case)

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
                case_context=case_context_str,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            store = _conversation_store.setdefault(cid, [])
            store.extend([
                {"role": "user", "content": body.message},
                {"role": "assistant", "content": full_text},
            ])
            if len(store) > MAX_HISTORY_ENTRIES:
                _conversation_store[cid] = store[-MAX_HISTORY_ENTRIES:]

            save_exchange(cid, body.message, full_text, sources, confidence)

            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'confidence': round(confidence, 2), 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            logger.info("chat done cid=%r tokens=%d", cid, len(full_text))

        except Exception as exc:
            logger.error("LLM stream error cid=%r: %s", cid, exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not reach Ollama. Make sure it is running: ollama serve'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Onboarding Cases ──────────────────────────────────────────────────────── #


@app.post("/api/cases", tags=["onboarding"])
@limiter.limit("10/minute")
async def create_onboarding_case(request: Request, body: CreateCaseRequest) -> dict:
    case = create_case(
        employee_name=body.employee_name,
        employee_email=body.employee_email,
        employee_id=body.employee_id,
        department=body.department,
        role=body.role,
        manager_name=body.manager_name,
        start_date=body.start_date,
    )
    return case


@app.get("/api/cases/{case_id}", tags=["onboarding"])
async def get_onboarding_case(case_id: str) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/complete-item", tags=["onboarding"])
async def mark_item_complete(case_id: str, body: CompleteItemRequest) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    updated = complete_item(case_id, body.stage_id, body.item_id)
    return updated  # type: ignore[return-value]


@app.post("/api/cases/{case_id}/advance-stage", tags=["onboarding"])
async def advance_onboarding_stage(case_id: str) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    updated = advance_stage(case_id)
    return updated  # type: ignore[return-value]


@app.post("/api/cases/{case_id}/escalate", tags=["onboarding"])
@limiter.limit("5/minute")
async def escalate_case(request: Request, case_id: str, body: EscalateRequest) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return create_escalation(case_id, body.reason, body.escalated_by)


# ── Admin ─────────────────────────────────────────────────────────────────── #


@app.get("/api/admin/cases", tags=["admin"])
async def list_cases(limit: int = 200) -> list[dict]:
    return get_all_cases(limit=limit)


# ── Document upload ───────────────────────────────────────────────────────── #


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
    return UploadResponse(filename=filename, sections_added=added, total_kb_sections=knowledge_base.section_count)


# ── Feedback ──────────────────────────────────────────────────────────────── #


@app.post("/api/feedback", response_model=FeedbackResponse, tags=["chat"])
@limiter.limit("30/minute")
async def feedback(request: Request, body: FeedbackRequest) -> FeedbackResponse:
    save_feedback(body.messageId, body.conversationId, body.feedback)
    return FeedbackResponse(status="recorded")


# ── Audit ─────────────────────────────────────────────────────────────────── #


@app.get("/api/audit/conversations", tags=["audit"])
async def audit_conversations(limit: int = 100) -> list[dict]:
    return get_conversations(limit=limit)


@app.get("/api/audit/conversations/{conversation_id}", tags=["audit"])
async def audit_conversation_detail(conversation_id: str) -> list[dict]:
    messages = get_conversation_messages(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@app.get("/api/audit/feedback", tags=["audit"])
async def audit_feedback() -> list[dict]:
    return get_feedback_summary()
