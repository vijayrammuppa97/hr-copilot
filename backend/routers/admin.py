from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import ADMIN_TOKEN
from database import (
    get_conversations, get_conversation_messages, get_feedback_summary,
    get_admin_stats, get_top_interactions, get_confidence_distribution, get_messages_over_time,
)
from user_manager import get_all_users
from case_manager import get_all_cases
from evaluation import get_evaluation_summary
from dependencies import get_knowledge_base

router  = APIRouter(tags=["admin"])
_bearer = HTTPBearer(auto_error=False)


def require_admin(credentials: HTTPAuthorizationCredentials | None = Security(_bearer)) -> None:
    if not credentials or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# ── Admin endpoints ────────────────────────────────────────────────────────── #

@router.get("/api/admin/stats")
async def admin_stats(_: None = Depends(require_admin)) -> dict:
    return get_admin_stats()


@router.get("/api/admin/top-interactions")
async def admin_top_interactions(limit: int = 20, _: None = Depends(require_admin)) -> list[dict]:
    return get_top_interactions(limit=limit)


@router.get("/api/admin/confidence-distribution")
async def admin_confidence_dist(_: None = Depends(require_admin)) -> list[dict]:
    return get_confidence_distribution()


@router.get("/api/admin/messages-over-time")
async def admin_messages_over_time(days: int = 30, _: None = Depends(require_admin)) -> list[dict]:
    return get_messages_over_time(days=days)


@router.get("/api/admin/evaluation")
async def admin_evaluation(_: None = Depends(require_admin)) -> dict:
    return get_evaluation_summary()


@router.get("/api/admin/users")
async def admin_users(limit: int = 500, _: None = Depends(require_admin)) -> list[dict]:
    return get_all_users(limit=limit)


@router.get("/api/admin/cases")
async def admin_cases(limit: int = 200, _: None = Depends(require_admin)) -> list[dict]:
    return get_all_cases(limit=limit)


@router.get("/api/admin/kb-sources")
async def admin_kb_sources(_: None = Depends(require_admin)) -> dict:
    kb = get_knowledge_base()
    return {
        "sources":          kb.source_files,
        "total_sections":   kb.section_count,
        "semantic_enabled": kb.semantic_enabled,
    }


# ── Audit endpoints ────────────────────────────────────────────────────────── #

@router.get("/api/audit/conversations", tags=["audit"])
async def audit_conversations(limit: int = 100) -> list[dict]:
    return get_conversations(limit=limit)


@router.get("/api/audit/conversations/{conversation_id}", tags=["audit"])
async def audit_conversation_detail(conversation_id: str) -> list[dict]:
    messages = get_conversation_messages(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@router.get("/api/audit/feedback", tags=["audit"])
async def audit_feedback() -> list[dict]:
    return get_feedback_summary()
