"""
HR Onboarding Copilot — FastAPI backend v4.0

New in this version:
  - Semantic search (Ollama embeddings + cosine similarity)
  - Fuzzy/typo-tolerant retrieval (difflib expansion)
  - Recursive chunking with overlap
  - Multi-doc admin folder (data/knowledge_docs/) + file watcher
  - User identity: random username + UUID user_id
  - Session history tree per user
  - Evaluation logging: Recall@3 + faithfulness per query
  - Admin observability: stats, top-20 interactions, charts
  - Admin auth via bearer token (ADMIN_TOKEN env var)
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from knowledge_loader import KnowledgeBase
from llm_handler import LLMHandler
from document_loader import parse_document, SUPPORTED_EXTENSIONS
from document_watcher import DocumentWatcher
from database import (
    init_db, save_exchange, save_feedback,
    get_conversations, get_conversation_messages, get_feedback_summary,
    get_admin_stats, get_top_interactions, get_confidence_distribution, get_messages_over_time,
)
from case_manager import (
    create_case, get_case, get_all_cases,
    complete_item, advance_stage, create_escalation, build_case_context,
)
from user_manager import (
    register_user, get_user, touch_user, get_user_sessions,
    get_all_users, create_session, update_session, generate_username, generate_user_id,
)
from evaluation import log_evaluation, get_evaluation_summary

# ── Logging ──────────────────────────────────────────────────────────────── #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("hr_copilot")

# ── Environment ──────────────────────────────────────────────────────────── #

load_dotenv()

KB_PATH      = os.getenv("KB_PATH", "../data/knowledge_base.md")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ADMIN_TOKEN  = os.getenv("ADMIN_TOKEN", "hr-admin-secret-2024")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]

_conversation_store: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY_ENTRIES = 12

# ── Admin auth ────────────────────────────────────────────────────────────── #

_bearer = HTTPBearer(auto_error=False)


def require_admin(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> None:
    if not credentials or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# ── App setup ─────────────────────────────────────────────────────────────── #

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

knowledge_base: KnowledgeBase
llm_handler:    LLMHandler
doc_watcher:    DocumentWatcher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global knowledge_base, llm_handler, doc_watcher
    logger.info("Starting HR Onboarding Copilot v4 — model=%s", OLLAMA_MODEL)
    init_db()
    knowledge_base = KnowledgeBase(KB_PATH, embed_host=OLLAMA_HOST)
    llm_handler    = LLMHandler(model=OLLAMA_MODEL, host=OLLAMA_HOST)
    doc_watcher    = DocumentWatcher(knowledge_base)
    doc_watcher.start()
    yield
    doc_watcher.stop()
    logger.info("Shutting down")


app = FastAPI(
    title="HR Onboarding Copilot API",
    version="4.0.0",
    description="Enterprise HR Onboarding — semantic RAG, workflow orchestration, user management, observability",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Schemas ──────────────────────────────────────────────────────────────── #


class ChatRequest(BaseModel):
    message:        str       = Field(..., min_length=1, max_length=2000)
    conversationId: str       = Field(..., min_length=1, max_length=100)
    caseId:         str | None = Field(default=None, max_length=100)
    userId:         str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be blank")
        return v

    @field_validator("conversationId")
    @classmethod
    def strip_cid(cls, v: str) -> str:
        return v.strip()


class FeedbackRequest(BaseModel):
    messageId:      str = Field(..., min_length=1, max_length=100)
    conversationId: str = Field(..., min_length=1, max_length=100)
    feedback:       Literal["helpful", "not_helpful"]


class RegisterUserRequest(BaseModel):
    user_id:  str | None = None
    username: str | None = None


class CreateCaseRequest(BaseModel):
    employee_name:  str = Field(..., min_length=1, max_length=200)
    employee_email: str = Field(..., min_length=3, max_length=200)
    employee_id:    str = Field(default="", max_length=100)
    department:     str = Field(default="", max_length=200)
    role:           str = Field(default="", max_length=200)
    manager_name:   str = Field(default="", max_length=200)
    start_date:     str = Field(default="", max_length=50)

    @field_validator("employee_name", "employee_email")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()


class CompleteItemRequest(BaseModel):
    stage_id: str = Field(..., min_length=1, max_length=100)
    item_id:  str = Field(..., min_length=1, max_length=100)


class EscalateRequest(BaseModel):
    reason:       str = Field(..., min_length=1, max_length=1000)
    escalated_by: str = Field(default="employee", max_length=50)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# ── Exception handler ─────────────────────────────────────────────────────── #

@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Health ────────────────────────────────────────────────────────────────── #

@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    return {
        "status":           "healthy",
        "kb_sections":      knowledge_base.section_count,
        "kb_sources":       knowledge_base.source_files,
        "semantic_enabled": knowledge_base.semantic_enabled,
        "model":            OLLAMA_MODEL,
        "embed_model":      os.getenv("EMBED_MODEL", "nomic-embed-text"),
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }


# ── Retrieval debug — diagnose what chunks are retrieved for a query ───────── #

@app.get("/api/debug/retrieve", tags=["ops"])
async def debug_retrieve(q: str, top_k: int = 5) -> dict:
    """
    Show exactly which chunks are retrieved for a query.
    Use this to diagnose retrieval failures before blaming the LLM.

    Example: GET /api/debug/retrieve?q=paternity+leave
    """
    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, knowledge_base.search, q)
    return {
        "query":   q,
        "results": [
            {
                "rank":    i + 1,
                "section": r["section"],
                "score":   r.get("score", 0),
                "preview": r["content"][:300],
            }
            for i, r in enumerate(results[:top_k])
        ],
    }


# ── User management ───────────────────────────────────────────────────────── #

@app.post("/api/users/register", tags=["users"])
async def register(body: RegisterUserRequest) -> dict:
    uid      = body.user_id  or generate_user_id()
    username = body.username or generate_username()
    existing = get_user(uid)
    if existing:
        touch_user(uid)
        return existing
    return register_user(uid, username)


@app.get("/api/users/{user_id}", tags=["users"])
async def get_user_profile(user_id: str) -> dict:
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    touch_user(user_id)
    return user


@app.get("/api/users/{user_id}/sessions", tags=["users"])
async def user_sessions(user_id: str) -> list[dict]:
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return get_user_sessions(user_id)


# ── Chat ──────────────────────────────────────────────────────────────────── #

@app.post("/api/chat", tags=["chat"])
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    cid = body.conversationId
    logger.info("chat cid=%r user=%r case=%r msg=%r", cid, body.userId, body.caseId, body.message[:80])

    # Track session
    if body.userId:
        create_session(body.userId, cid, body.caseId)
        update_session(cid)

    # Build case context
    case_context_str: str | None = None
    if body.caseId:
        case = get_case(body.caseId)
        if case:
            case_context_str = build_case_context(case)

    history    = _conversation_store.get(cid, [])[-MAX_HISTORY_ENTRIES:]
    # Run embedding search in thread pool to avoid blocking the event loop
    loop       = asyncio.get_event_loop()
    kb_results = await loop.run_in_executor(None, knowledge_base.search, body.message)
    sources    = [r["section"] for r in kb_results[:3]]
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
                {"role": "user",      "content": body.message},
                {"role": "assistant", "content": full_text},
            ])
            if len(store) > MAX_HISTORY_ENTRIES:
                _conversation_store[cid] = store[-MAX_HISTORY_ENTRIES:]

            save_exchange(cid, body.message, full_text, sources, confidence)

            # Log evaluation metrics
            eval_metrics = log_evaluation(cid, body.message, kb_results, full_text, k=3)

            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'confidence': round(confidence, 2), 'eval': eval_metrics, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

        except Exception as exc:
            logger.error("LLM stream error cid=%r: %s", cid, exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not reach Ollama. Make sure it is running: ollama serve'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Feedback ──────────────────────────────────────────────────────────────── #

@app.post("/api/feedback", tags=["chat"])
@limiter.limit("30/minute")
async def feedback(request: Request, body: FeedbackRequest) -> dict:
    save_feedback(body.messageId, body.conversationId, body.feedback)
    return {"status": "recorded"}


# ── Document upload ───────────────────────────────────────────────────────── #

@app.post("/api/upload", tags=["documents"])
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    sections = parse_document(data, filename)
    if not sections:
        raise HTTPException(status_code=422, detail="Could not extract content from file")
    added = knowledge_base.add_sections(sections, source_file=filename)
    return {"filename": filename, "sections_added": added, "total_kb_sections": knowledge_base.section_count}


# ── Onboarding cases ──────────────────────────────────────────────────────── #

@app.post("/api/cases", tags=["onboarding"])
@limiter.limit("10/minute")
async def create_onboarding_case(request: Request, body: CreateCaseRequest) -> dict:
    return create_case(
        employee_name=body.employee_name,
        employee_email=body.employee_email,
        employee_id=body.employee_id,
        department=body.department,
        role=body.role,
        manager_name=body.manager_name,
        start_date=body.start_date,
    )


@app.get("/api/cases/{case_id}", tags=["onboarding"])
async def get_onboarding_case(case_id: str) -> dict:
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/complete-item", tags=["onboarding"])
async def mark_item_complete(case_id: str, body: CompleteItemRequest) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return complete_item(case_id, body.stage_id, body.item_id)  # type: ignore[return-value]


@app.post("/api/cases/{case_id}/advance-stage", tags=["onboarding"])
async def advance_onboarding_stage(case_id: str) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return advance_stage(case_id)  # type: ignore[return-value]


@app.post("/api/cases/{case_id}/escalate", tags=["onboarding"])
@limiter.limit("5/minute")
async def escalate_case(request: Request, case_id: str, body: EscalateRequest) -> dict:
    if not get_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return create_escalation(case_id, body.reason, body.escalated_by)


# ── Admin — protected endpoints ───────────────────────────────────────────── #

@app.get("/api/admin/stats", tags=["admin"])
async def admin_stats(_: None = Depends(require_admin)) -> dict:
    return get_admin_stats()


@app.get("/api/admin/top-interactions", tags=["admin"])
async def admin_top_interactions(limit: int = 20, _: None = Depends(require_admin)) -> list[dict]:
    return get_top_interactions(limit=limit)


@app.get("/api/admin/confidence-distribution", tags=["admin"])
async def admin_confidence_dist(_: None = Depends(require_admin)) -> list[dict]:
    return get_confidence_distribution()


@app.get("/api/admin/messages-over-time", tags=["admin"])
async def admin_messages_over_time(days: int = 30, _: None = Depends(require_admin)) -> list[dict]:
    return get_messages_over_time(days=days)


@app.get("/api/admin/evaluation", tags=["admin"])
async def admin_evaluation(_: None = Depends(require_admin)) -> dict:
    return get_evaluation_summary()


@app.get("/api/admin/users", tags=["admin"])
async def admin_users(limit: int = 500, _: None = Depends(require_admin)) -> list[dict]:
    return get_all_users(limit=limit)


@app.get("/api/admin/cases", tags=["admin"])
async def admin_cases(limit: int = 200, _: None = Depends(require_admin)) -> list[dict]:
    return get_all_cases(limit=limit)


@app.get("/api/admin/kb-sources", tags=["admin"])
async def admin_kb_sources(_: None = Depends(require_admin)) -> dict:
    return {
        "sources":          knowledge_base.source_files,
        "total_sections":   knowledge_base.section_count,
        "semantic_enabled": knowledge_base.semantic_enabled,
    }


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
