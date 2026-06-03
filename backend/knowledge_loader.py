"""
HR Knowledge Base — multi-document, semantic search, fuzzy/typo-tolerant retrieval.

Search pipeline:
  1. Text normalisation  — lowercase, collapse hyphens, strip punctuation
  2. Fuzzy expansion     — difflib finds near-matches for each query token
  3. Policy keyword boost — 2.5× multiplier when query matches known HR section names
                            (Annual Leave, Sick Leave, Paternity Leave, Remote Work, etc.)
  4. Semantic search     — cosine similarity on Ollama nomic-embed-text embeddings (primary)
  5. Keyword re-rank     — Jaccard boosts exact/fuzzy matches (secondary signal)
  6. Score blend         — 0.75 × semantic + 0.25 × keyword
  7. Similarity threshold — results below 0.25 are dropped to prevent irrelevant retrieval
  8. Per-query logging   — every retrieved chunk is logged so failures can be diagnosed

Admin folder:
  All files inside data/knowledge_docs/ are indexed on startup.
  The DocumentWatcher (document_watcher.py) calls reload_file() on changes.
"""

import difflib
import logging
import re
from pathlib import Path

from embeddings import EmbeddingGenerator, VectorStore
from document_loader import parse_document

logger = logging.getLogger("hr_copilot.knowledge")

_STOP_WORDS: frozenset[str] = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "could should may might shall can need to of in for on with at by from as "
    "into through about over after what how when where who which that this and "
    "or but if then not no i my me we our you your it its up out so just".split()
)

# Similarity threshold — chunks below this score are dropped from results.
# Prevents completely irrelevant sections polluting the LLM context.
SIMILARITY_THRESHOLD = 0.25

# Policy section keyword map — when a query mentions these terms,
# chunks whose headings contain the matched keywords receive a 2.5× boost.
# This directly fixes the "paternity leave → Jury Duty" class of errors.
_POLICY_KEYWORDS: dict[str, list[str]] = {
    "annual leave":        ["annual", "leave", "vacation", "holiday"],
    "sick leave":          ["sick", "medical", "illness", "doctor", "certificate"],
    "paternity leave":     ["paternity", "father", "paternal"],
    "maternity leave":     ["maternity", "mother", "maternal", "pregnancy"],
    "parental leave":      ["parental", "parent", "baby", "newborn", "adoption"],
    "remote work":         ["remote", "wfh", "work from home", "hybrid"],
    "grievance":           ["grievance", "complaint", "formal", "dispute"],
    "performance":         ["performance", "review", "appraisal", "pip"],
    "resignation":         ["resign", "notice", "termination", "leaving"],
    "expense":             ["expense", "reimbursement", "claim", "receipt"],
    "equipment":           ["equipment", "laptop", "device", "hardware", "stolen", "lost"],
    "harassment":          ["harassment", "bully", "posh", "misconduct"],
    "overtime":            ["overtime", "extra hours", "additional hours"],
    "carry forward":       ["carry", "carryover", "rollover", "unused leave"],
    "emergency leave":     ["emergency", "bereavement", "compassionate", "funeral"],
    "jury duty":           ["jury", "civic", "court", "witness"],
    "training":            ["training", "learning", "development", "course", "lms"],
    "payroll":             ["payroll", "salary", "pay", "bank", "tax", "deduction"],
    "onboarding":          ["onboarding", "joining", "induction", "first day"],
}


def _policy_title_boost(query_tokens: set[str], section_title: str) -> float:
    """
    Returns a multiplier (1.0 = no boost, 2.5 = strong boost) when query
    tokens match a known policy section keyword group AND the section title
    also contains those keywords.
    """
    title_lower = section_title.lower()
    for _group, keywords in _POLICY_KEYWORDS.items():
        # Check if query mentions any keyword in the group
        query_matches = any(kw in " ".join(query_tokens) for kw in keywords)
        if not query_matches:
            continue
        # Check if the section title also contains any keyword from the group
        title_matches = any(kw in title_lower for kw in keywords)
        if title_matches:
            return 2.5
    return 1.0


# ── Text helpers ─────────────────────────────────────────────────────────── #

def _normalise(text: str) -> str:
    """Lowercase, collapse hyphens/underscores to space, strip non-alpha."""
    text = text.lower()
    text = re.sub(r"[-_/]", " ", text)          # new-jersey → new jersey
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z]{2,}\b", _normalise(text))
    return [t for t in tokens if t not in _STOP_WORDS]


def _tokenize_set(text: str) -> set[str]:
    return set(_tokenize(text))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _fuzzy_expand(query_tokens: list[str], vocab: set[str], cutoff: float = 0.80) -> set[str]:
    """
    For each query token find close vocab matches using difflib.
    Handles: "new jrsey" → "new jersey", "benefts" → "benefits"
    """
    expanded: set[str] = set(query_tokens)
    for tok in query_tokens:
        matches = difflib.get_close_matches(tok, vocab, n=3, cutoff=cutoff)
        expanded.update(matches)
    return expanded


# ── Knowledge section ─────────────────────────────────────────────────────── #

class KnowledgeSection:
    __slots__ = ("section", "content", "tokens", "source_file")

    def __init__(self, section: str, content: str, source_file: str = "") -> None:
        self.section     = section
        self.content     = content
        self.source_file = source_file
        self.tokens: set[str] = _tokenize_set(f"{section} {content}")


# ── Knowledge base ────────────────────────────────────────────────────────── #

class KnowledgeBase:
    """
    Multi-document knowledge base with:
    - Semantic vector search (primary)
    - Fuzzy-tolerant keyword matching (secondary)
    - Vocabulary-aware typo correction
    """

    DOCS_FOLDER = Path(__file__).parent.parent / "data" / "knowledge_docs"

    def __init__(self, kb_path: str, embed_host: str = "http://localhost:11434") -> None:
        self._primary_path = Path(kb_path)
        self._sections: list[KnowledgeSection] = []
        self._vocab: set[str] = set()

        # Semantic store (may be unavailable if Ollama is down at startup)
        try:
            self._gen   = EmbeddingGenerator(host=embed_host)
            self._store = VectorStore(self._gen)
            self._semantic_ok = True
        except Exception as exc:
            logger.warning("Embedding store unavailable — falling back to keyword search: %s", exc)
            self._store = None
            self._gen   = None
            self._semantic_ok = False

        self._load_all()

    # ── Loading ───────────────────────────────────────────────────────────── #

    def _load_all(self) -> None:
        # Primary knowledge base
        if self._primary_path.exists():
            self._index_file(self._primary_path)

        # Admin multi-doc folder
        self.DOCS_FOLDER.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.DOCS_FOLDER.iterdir()):
            if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".csv", ".txt", ".md", ".text"}:
                self._index_file(path)

        self._rebuild_vocab()
        logger.info(
            "KnowledgeBase ready — %d sections, %d vocab tokens, semantic=%s",
            len(self._sections), len(self._vocab), self._semantic_ok,
        )

    def _index_file(self, path: Path) -> None:
        try:
            data    = path.read_bytes()
            parsed  = parse_document(data, path.name)
            added   = 0
            for item in parsed:
                sec  = item.get("section", "").strip()
                body = item.get("content", "").strip()
                if not sec or not body:
                    continue
                ks = KnowledgeSection(sec, body, source_file=path.name)
                self._sections.append(ks)
                if self._store:
                    self._store.add(sec, body, source_file=path.name)
                added += 1
            logger.info("Indexed %d sections from %s", added, path.name)
        except Exception as exc:
            logger.error("Failed to index %s: %s", path, exc)

    def reload_file(self, path: Path) -> int:
        """Called by DocumentWatcher when a file changes. Returns sections added."""
        # Remove old sections from this file
        before = len(self._sections)
        self._sections = [s for s in self._sections if s.source_file != path.name]
        if self._store:
            # Rebuild vector store without this file then re-add
            self._store.clear()
            for s in self._sections:
                self._store.add(s.section, s.content, s.source_file)

        self._index_file(path)
        self._rebuild_vocab()
        added = len(self._sections) - (before - (before - len([s for s in self._sections if s.source_file == path.name])))
        return max(0, len(self._sections) - before + len([s for s in self._sections if s.source_file == path.name]))

    def _rebuild_vocab(self) -> None:
        vocab: set[str] = set()
        for s in self._sections:
            vocab.update(s.tokens)
        self._vocab = vocab

    # ── Search ────────────────────────────────────────────────────────────── #

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        """
        Retrieve the top_k most relevant sections for a query.

        Pipeline:
          1. Normalise + fuzzy-expand query tokens
          2. Semantic similarity (nomic-embed-text cosine)
          3. Keyword Jaccard re-rank
          4. Policy section title keyword boost (2.5×)
          5. Similarity threshold filter (drops score < SIMILARITY_THRESHOLD)
          6. Log every retrieved chunk for diagnosis
        """
        if not self._sections:
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return [
                {"section": s.section, "content": s.content, "source_file": s.source_file, "score": 0.0}
                for s in self._sections[:top_k]
            ]

        # 1. Fuzzy-expand to fix typos
        expanded_tokens = _fuzzy_expand(q_tokens, self._vocab, cutoff=0.80)

        # 2. Semantic scores from vector store
        semantic_scores: dict[int, float] = {}
        if self._store and self._semantic_ok:
            # Request 3× top_k candidates so re-ranking has room to work
            sem_results = self._store.search(query, top_k=min(top_k * 3, 30))
            for res in sem_results:
                for i, s in enumerate(self._sections):
                    if s.section == res["section"] and s.content == res["content"]:
                        semantic_scores[i] = res.get("score", 0.0)
                        break

        # 3+4. Keyword + policy boost scoring
        scored: list[tuple[float, int]] = []
        for i, sec in enumerate(self._sections):
            kw_score = _jaccard(expanded_tokens, sec.tokens)

            # 3a. Heading token match bonus
            if expanded_tokens & _tokenize_set(sec.section):
                kw_score *= 1.4

            # 4. Policy keyword title boost — biggest fix for wrong-section retrieval
            policy_boost = _policy_title_boost(expanded_tokens, sec.section)
            kw_score *= policy_boost

            sem_score = semantic_scores.get(i, 0.0)

            if self._semantic_ok and sem_score > 0:
                combined = 0.75 * sem_score + 0.25 * kw_score
            else:
                combined = kw_score  # fallback to keyword-only

            # Apply policy boost to combined score too
            combined *= policy_boost if policy_boost > 1.0 and sem_score > 0 else 1.0

            if combined > 0:
                scored.append((combined, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 5. Similarity threshold — drop irrelevant results
        results = []
        for score, idx in scored[:top_k * 2]:   # over-fetch then filter
            if score < SIMILARITY_THRESHOLD and len(results) >= 3:
                break   # always keep at least 3 even if below threshold
            s = self._sections[idx]
            results.append({
                "section":     s.section,
                "content":     s.content,
                "source_file": s.source_file,
                "score":       round(score, 4),
            })
            if len(results) >= top_k:
                break

        # 6. Log retrieved chunks for every query — critical for diagnosis
        logger.info(
            "RETRIEVE query=%r top=%d threshold=%.2f",
            query[:80], len(results), SIMILARITY_THRESHOLD,
        )
        for rank, r in enumerate(results, 1):
            logger.info(
                "  [%d] score=%.4f  section=%r  preview=%r",
                rank, r["score"], r["section"], r["content"][:120],
            )

        return results

    # ── Mutation ──────────────────────────────────────────────────────────── #

    def add_sections(self, sections: list[dict], source_file: str = "upload") -> int:
        added = 0
        for item in sections:
            sec  = item.get("section", "").strip()
            body = item.get("content", "").strip()
            if sec and body:
                ks = KnowledgeSection(sec, body, source_file=source_file)
                self._sections.append(ks)
                if self._store:
                    self._store.add(sec, body, source_file=source_file)
                added += 1
        if added:
            self._rebuild_vocab()
            logger.info("Added %d sections from upload (total=%d)", added, len(self._sections))
        return added

    # ── Properties ───────────────────────────────────────────────────────── #

    @property
    def section_count(self) -> int:
        return len(self._sections)

    @property
    def source_files(self) -> list[str]:
        seen: set[str] = set()
        files: list[str] = []
        for s in self._sections:
            if s.source_file and s.source_file not in seen:
                seen.add(s.source_file)
                files.append(s.source_file)
        return files

    @property
    def semantic_enabled(self) -> bool:
        return self._semantic_ok
