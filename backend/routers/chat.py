import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import MAX_HISTORY_ENTRIES
from database import save_exchange, save_feedback, get_history_from_db
from user_manager import get_user, create_session, update_session, build_profile_context, update_user_profile
from case_manager import get_case, build_case_context
from evaluation import log_evaluation
from profile_extractor import extract_profile_facts
from followup_generator import generate_follow_up_questions
from models.chat import ChatRequest, FeedbackRequest

# Injected by main.py lifespan — see dependencies.py
from dependencies import get_knowledge_base, get_llm_handler, get_query_rewriter

router  = APIRouter(prefix="/api", tags=["chat"])
limiter = Limiter(key_func=get_remote_address)
logger  = logging.getLogger("hr_copilot.chat")


@router.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    cid = body.conversationId
    logger.info("chat cid=%r user=%r case=%r msg=%r", cid, body.userId, body.caseId, body.message[:80])

    knowledge_base = get_knowledge_base()
    llm_handler    = get_llm_handler()
    query_rewriter = get_query_rewriter()

    if body.userId:
        create_session(body.userId, cid, body.caseId)
        update_session(cid)

    case_context_str: str | None = None
    if body.caseId:
        case = get_case(body.caseId)
        if case:
            case_context_str = build_case_context(case)

    user_profile_ctx: str | None = None
    user_data: dict | None = None
    if body.userId:
        user_data = get_user(body.userId)
        if user_data:
            user_profile_ctx = build_profile_context(user_data)

    history       = get_history_from_db(cid, limit=MAX_HISTORY_ENTRIES)
    extra_queries = query_rewriter.expand(body.message)[1:]
    loop          = asyncio.get_event_loop()
    kb_results    = await loop.run_in_executor(
        None, lambda: knowledge_base.search(body.message, extra_queries=extra_queries)
    )
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
                user_profile=user_profile_ctx,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

            save_exchange(cid, body.message, full_text, sources, confidence)

            if body.userId:
                facts = extract_profile_facts(body.message)
                if facts:
                    existing  = user_data or {}
                    new_facts = {k: v for k, v in facts.items() if existing.get(k) is None}
                    if new_facts:
                        update_user_profile(body.userId, **new_facts)
                        logger.info("Profile updated user=%r facts=%r", body.userId, new_facts)

            eval_metrics = log_evaluation(cid, body.message, kb_results, full_text, k=3)
            follow_ups   = generate_follow_up_questions(kb_results)

            yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'confidence': round(confidence, 2), 'follow_up_questions': follow_ups, 'eval': eval_metrics, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

        except Exception as exc:
            logger.error("LLM stream error cid=%r: %s", cid, exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not reach Ollama. Make sure it is running: ollama serve'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/feedback")
@limiter.limit("30/minute")
async def feedback(request: Request, body: FeedbackRequest) -> dict:
    save_feedback(body.messageId, body.conversationId, body.feedback)
    return {"status": "recorded"}
