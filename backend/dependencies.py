"""
Shared application-level singletons (KB, LLM, query rewriter).
Populated during FastAPI lifespan startup in main.py.
Routers call the getters instead of importing globals directly.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge_loader import KnowledgeBase
    from llm_handler import LLMHandler
    from query_rewriter import QueryRewriter

_knowledge_base: "KnowledgeBase | None" = None
_llm_handler:    "LLMHandler | None"    = None
_query_rewriter: "QueryRewriter | None" = None


def set_knowledge_base(kb: "KnowledgeBase") -> None:
    global _knowledge_base
    _knowledge_base = kb


def set_llm_handler(llm: "LLMHandler") -> None:
    global _llm_handler
    _llm_handler = llm


def set_query_rewriter(qr: "QueryRewriter") -> None:
    global _query_rewriter
    _query_rewriter = qr


def get_knowledge_base() -> "KnowledgeBase":
    if _knowledge_base is None:
        raise RuntimeError("KnowledgeBase not initialised — check lifespan startup")
    return _knowledge_base


def get_llm_handler() -> "LLMHandler":
    if _llm_handler is None:
        raise RuntimeError("LLMHandler not initialised — check lifespan startup")
    return _llm_handler


def get_query_rewriter() -> "QueryRewriter":
    if _query_rewriter is None:
        raise RuntimeError("QueryRewriter not initialised — check lifespan startup")
    return _query_rewriter
