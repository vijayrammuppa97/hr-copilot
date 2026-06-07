"""
HR Onboarding Copilot — FastAPI entry point.

Responsibilities (this file only):
  - App factory + lifespan (startup / shutdown)
  - Middleware (CORS, rate limiting)
  - Include all routers
  - Health check

All routes live in routers/. All Pydantic schemas live in models/.
Business logic stays in the flat service files (auth.py, user_manager.py, etc.).
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import OLLAMA_MODEL, OLLAMA_HOST, KB_PATH, CORS_ORIGINS
from database import init_db, seed_admin_user
from knowledge_loader import KnowledgeBase
from llm_handler import LLMHandler
from query_rewriter import QueryRewriter
from document_watcher import DocumentWatcher
from dependencies import set_knowledge_base, set_llm_handler, set_query_rewriter, get_knowledge_base
from routers import (
    auth_router, chat_router, users_router,
    cases_router, admin_router, documents_router,
)

# ── Logging ──────────────────────────────────────────────────────────────── #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("hr_copilot")

# ── Lifespan ──────────────────────────────────────────────────────────────── #

_doc_watcher: DocumentWatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _doc_watcher
    import hashlib, secrets as _secrets
    logger.info("Starting HR Copilot — model=%s", OLLAMA_MODEL)
    init_db()
    _admin_salt = "a3f8c2d1e5b04917"
    _admin_hash = hashlib.sha256(f"{_admin_salt}Adm!nHR#2025".encode()).hexdigest()
    seed_admin_user(
        email="diana.foster@acme.com",
        full_name="Diana Foster",
        password_hash=_admin_hash,
        salt=_admin_salt,
    )
    kb = KnowledgeBase(KB_PATH, embed_host=OLLAMA_HOST)
    set_knowledge_base(kb)
    set_llm_handler(LLMHandler(model=OLLAMA_MODEL, host=OLLAMA_HOST))
    set_query_rewriter(QueryRewriter(model=OLLAMA_MODEL, host=OLLAMA_HOST))
    _doc_watcher = DocumentWatcher(kb)
    _doc_watcher.start()
    yield
    if _doc_watcher:
        _doc_watcher.stop()
    logger.info("Shutting down")

# ── App ───────────────────────────────────────────────────────────────────── #

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

app = FastAPI(
    title="HR Onboarding Copilot API",
    version="5.0.0",
    description="Enterprise HR Onboarding — hybrid RAG, workflow orchestration, auth, observability",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Routers ───────────────────────────────────────────────────────────────── #

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(cases_router)
app.include_router(admin_router)
app.include_router(documents_router)

# ── Health ────────────────────────────────────────────────────────────────── #

@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    from datetime import datetime, timezone
    import os
    kb = get_knowledge_base()
    return {
        "status":           "healthy",
        "model":            OLLAMA_MODEL,
        "embed_model":      os.getenv("EMBED_MODEL", "bge-m3"),
        "kb_sections":      kb.section_count,
        "kb_sources":       kb.source_files,
        "semantic_enabled": kb.semantic_enabled,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }


# ── Global exception handler ─────────────────────────────────────────────── #

@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
