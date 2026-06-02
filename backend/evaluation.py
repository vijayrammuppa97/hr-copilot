"""
Retrieval and generation quality evaluation.

Recall@K  — fraction of top-K retrieved sections that are "relevant"
            (proxy: semantic overlap score > threshold, since we have no labels)

Faithfulness — fraction of the generated answer that is grounded in
               the retrieved context (n-gram overlap proxy)
               Range: 0.0 (hallucinated) → 1.0 (fully grounded)

RAGAS note: For production RAGAS integration install `ragas` and point it at
            your OpenAI-compatible endpoint. This module provides a lightweight
            local approximation that works without external API keys.
"""

import logging
import re
from datetime import datetime, timezone

from database import _connect

logger = logging.getLogger("hr_copilot.eval")


# ── Text helpers ─────────────────────────────────────────────────────────── #

def _ngrams(text: str, n: int = 3) -> set[str]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    return {" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)}


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"\b\w{3,}\b", text.lower()))


# ── Recall@K ─────────────────────────────────────────────────────────────── #

def recall_at_k(retrieved: list[dict], query: str, k: int = 3, threshold: float = 0.15) -> float:
    """
    Proxy Recall@K without ground truth labels.

    A retrieved section is considered "relevant" if its content shares
    meaningful token overlap with the query (Jaccard ≥ threshold).
    This is an approximation — true Recall@K requires labelled test sets.
    """
    if not retrieved:
        return 0.0
    q_tokens = _token_set(query)
    if not q_tokens:
        return 0.0

    top_k   = retrieved[:k]
    hits    = 0
    for sec in top_k:
        s_tokens = _token_set(sec.get("content", "") + " " + sec.get("section", ""))
        overlap  = len(q_tokens & s_tokens) / len(q_tokens | s_tokens) if (q_tokens | s_tokens) else 0.0
        if overlap >= threshold:
            hits += 1
    return round(hits / k, 4)


# ── Faithfulness ─────────────────────────────────────────────────────────── #

def faithfulness(answer: str, context_sections: list[dict]) -> float:
    """
    Measures what fraction of the answer is grounded in the retrieved context.

    Method: 3-gram overlap between answer and all context combined.
    Score 1.0 = every 3-gram in the answer appears in context (fully grounded).
    Score 0.0 = no overlap (hallucinated).
    """
    if not answer or not context_sections:
        return 0.0
    context_text = " ".join(s.get("content", "") for s in context_sections)
    ans_ngrams   = _ngrams(answer, n=3)
    ctx_ngrams   = _ngrams(context_text, n=3)
    if not ans_ngrams:
        return 0.0
    grounded = len(ans_ngrams & ctx_ngrams) / len(ans_ngrams)
    return round(min(grounded, 1.0), 4)


# ── Semantic similarity score ─────────────────────────────────────────────── #

def relevance_score(query: str, retrieved: list[dict]) -> float:
    """Average retrieval score from semantic search (already computed in KnowledgeBase)."""
    if not retrieved:
        return 0.0
    scores = [r.get("score", 0.0) for r in retrieved if "score" in r]
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# ── Persist evaluation log ────────────────────────────────────────────────── #

def log_evaluation(
    conversation_id: str,
    query: str,
    retrieved: list[dict],
    answer: str,
    k: int = 3,
) -> dict:
    r_at_k   = recall_at_k(retrieved, query, k=k)
    faith    = faithfulness(answer, retrieved)
    rel_sc   = relevance_score(query, retrieved)
    now      = datetime.now(timezone.utc).isoformat()

    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO evaluation_log
                   (conversation_id, query, recall_at_k, faithfulness, relevance_score, k, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, query[:500], r_at_k, faith, rel_sc, k, now),
            )
    except Exception as exc:
        logger.error("Failed to log evaluation: %s", exc)

    return {
        "recall_at_k":      r_at_k,
        "faithfulness":     faith,
        "relevance_score":  rel_sc,
        "k":                k,
    }


def get_evaluation_summary(limit: int = 100) -> dict:
    """Aggregate eval metrics for the admin dashboard."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT AVG(recall_at_k) AS avg_recall,
                      AVG(faithfulness) AS avg_faith,
                      AVG(relevance_score) AS avg_relevance,
                      COUNT(*) AS total
               FROM (SELECT * FROM evaluation_log ORDER BY id DESC LIMIT ?)""",
            (limit,),
        ).fetchone()
        recent = conn.execute(
            """SELECT conversation_id, query, recall_at_k, faithfulness, relevance_score, timestamp
               FROM evaluation_log ORDER BY id DESC LIMIT 20""",
        ).fetchall()
    return {
        "averages": dict(rows) if rows else {},
        "recent":   [dict(r) for r in recent],
    }
