"""
Reranker — re-scores a candidate set of chunks against the original query.

Two implementations, used in priority order:

  1. CrossEncoderReranker (preferred)
     Uses sentence-transformers cross-encoder model.
     Install: pip install sentence-transformers
     Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~80 MB, fast on CPU)
     A cross-encoder sees (query, chunk) together, which is far more accurate
     than bi-encoder cosine similarity.

  2. OllamaReranker (fallback)
     Scores each (query, chunk) pair using the LLM with a 0-10 relevance prompt.
     Slower (one LLM call per chunk) but needs no new dependencies.
     Used when sentence-transformers is not installed.

  3. ScoreFusionReranker (always-available fallback)
     Weighted blend of BM25 + semantic scores.
     No ML inference — instant but less accurate than cross-encoder.

The reranker is the final gate before the LLM receives its context.
A good reranker dramatically reduces the chance of irrelevant chunks
reaching the LLM and causing hallucination.
"""

import logging
import math

import ollama

logger = logging.getLogger("hr_copilot.reranker")


# ── Helpers ───────────────────────────────────────────────────────────────── #

def _normalise_scores(results: list[dict], score_key: str) -> list[dict]:
    """Min-max normalise a score field to [0, 1]."""
    vals = [r.get(score_key, 0.0) for r in results]
    mn, mx = min(vals, default=0.0), max(vals, default=1.0)
    if mx == mn:
        return [{**r, score_key: 1.0} for r in results]
    return [{**r, score_key: (r.get(score_key, 0.0) - mn) / (mx - mn)} for r in results]


# ── 1. Cross-encoder (sentence-transformers) ──────────────────────────────── #

class CrossEncoderReranker:
    """Reranks using ms-marco-MiniLM-L-6-v2 cross-encoder."""

    MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self) -> None:
        self._encoder = None
        self._available = False
        try:
            from sentence_transformers import CrossEncoder
            self._encoder   = CrossEncoder(self.MODEL, max_length=512)
            self._available = True
            logger.info("CrossEncoder loaded: %s", self.MODEL)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — falling back to OllamaReranker. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as exc:
            logger.warning("CrossEncoder init failed (%s) — falling back", exc)

    @property
    def available(self) -> bool:
        return self._available

    def rerank(self, query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
        if not self._available or not candidates:
            return candidates[:top_k]
        pairs  = [(query, f"{c['section']}\n{c['content'][:600]}") for c in candidates]
        scores = self._encoder.predict(pairs)
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        out = []
        for score, doc in ranked[:top_k]:
            d = dict(doc)
            d["rerank_score"] = round(float(score), 4)
            d["score"] = round(
                1 / (1 + math.exp(-float(score))),   # sigmoid to [0, 1]
                4,
            )
            out.append(d)
        logger.info("CrossEncoder reranked %d → %d chunks", len(candidates), len(out))
        return out


# ── 2. Ollama-based LLM reranker (fallback) ───────────────────────────────── #

_RELEVANCE_PROMPT = """\
Rate how relevant this HR policy section is to the employee question.
Respond with only a number from 0 to 10 (10 = perfectly answers the question).

Question: {query}

Policy section ({section}):
{content}

Relevance score (0-10):"""


class OllamaReranker:
    """Scores each chunk with the LLM. Slow but accurate."""

    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self._model  = model
        self._client = ollama.Client(host=host)
        logger.info("OllamaReranker ready — model=%s", model)

    def rerank(self, query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
        if not candidates:
            return []
        scored = []
        for doc in candidates:
            try:
                resp = self._client.generate(
                    model=self._model,
                    prompt=_RELEVANCE_PROMPT.format(
                        query=query,
                        section=doc["section"],
                        content=doc["content"][:400],
                    ),
                    options={"num_predict": 5, "temperature": 0.0},
                    keep_alive=-1,
                )
                raw = resp["response"].strip().split()[0]
                score = float(raw) / 10.0
            except Exception:
                score = doc.get("score", 0.0)
            d = dict(doc)
            d["rerank_score"] = round(score, 4)
            d["score"] = round(score, 4)
            scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = [d for _, d in scored[:top_k]]
        logger.info("OllamaReranker scored %d → %d chunks", len(candidates), len(out))
        return out


# ── 3. Score-fusion reranker (always available) ───────────────────────────── #

class ScoreFusionReranker:
    """
    Blends BM25 + semantic scores. No ML inference required.
    Less accurate than cross-encoders but zero latency.
    """

    def rerank(self, query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
        if not candidates:
            return []
        normed_sem  = _normalise_scores(candidates, "score")
        normed_bm25 = _normalise_scores(normed_sem, "bm25_score")
        blended = []
        for doc in normed_bm25:
            sem   = doc.get("score", 0.0)
            bm25  = doc.get("bm25_score", 0.0)
            rrf   = doc.get("rrf_score", 0.0)
            final = 0.50 * sem + 0.30 * bm25 + 0.20 * rrf
            d = dict(doc)
            d["score"] = round(final, 4)
            blended.append(d)
        blended.sort(key=lambda x: x["score"], reverse=True)
        return blended[:top_k]


# ── Factory ───────────────────────────────────────────────────────────────── #

def build_reranker(ollama_model: str, ollama_host: str) -> object:
    """
    Returns the best available reranker:
    CrossEncoder > OllamaReranker > ScoreFusionReranker
    """
    ce = CrossEncoderReranker()
    if ce.available:
        return ce
    logger.info("Using OllamaReranker as cross-encoder is unavailable")
    return OllamaReranker(model=ollama_model, host=ollama_host)
