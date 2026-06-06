"""
BM25 index for keyword-based document retrieval.

BM25 (Best Match 25) is the gold-standard TF-IDF variant used in production
search engines (Elasticsearch, Solr). It beats simple Jaccard overlap because:
  - Penalises very long documents (length normalisation)
  - Saturates term frequency (diminishing returns for repeated terms)
  - Uses corpus-level IDF to downweight common words

Used as the keyword branch of the Hybrid Search pipeline:
  BM25 results + Semantic results → RRF fusion → Reranker
"""

import logging
import re

logger = logging.getLogger("hr_copilot.bm25")

_STOP_WORDS: frozenset[str] = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might shall can need to of in for on with at by from as "
    "into through about over after what how when where who which that this and "
    "or but if then not no i my me we our you your it its up out so just".split()
)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


class BM25Index:
    """
    In-memory BM25 index over KnowledgeSection objects.
    Rebuilt from scratch on every reload_file() call.
    """

    def __init__(self) -> None:
        self._docs: list[dict]        = []
        self._tokenized: list[list[str]] = []
        self._bm25 = None

    # ── Index management ──────────────────────────────────────────────────── #

    def build(self, sections: list[dict]) -> None:
        """Build BM25 index from a list of {section, content, source_file} dicts."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.error("rank-bm25 not installed — run: pip install rank-bm25")
            return

        self._docs      = list(sections)
        self._tokenized = [_tokenize(f"{s['section']} {s['content']}") for s in sections]
        self._bm25      = BM25Okapi(self._tokenized)
        logger.info("BM25 index built — %d documents", len(self._docs))

    def clear(self) -> None:
        self._docs      = []
        self._tokenized = []
        self._bm25      = None

    def add(self, section: str, content: str, source_file: str = "") -> None:
        """Incrementally add one section. Rebuilds the index."""
        self._docs.append({"section": section, "content": content, "source_file": source_file})
        self._tokenized.append(_tokenize(f"{section} {content}"))
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._tokenized)
        except ImportError:
            pass

    # ── Search ────────────────────────────────────────────────────────────── #

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """
        Returns up to top_k documents ranked by BM25 score.
        Results include a 'bm25_score' field.
        """
        if not self._bm25 or not self._docs:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores      = self._bm25.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            doc = dict(self._docs[idx])
            doc["bm25_score"] = round(float(scores[idx]), 4)
            results.append(doc)
        return results

    @property
    def doc_count(self) -> int:
        return len(self._docs)
