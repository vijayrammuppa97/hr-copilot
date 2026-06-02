"""
HR Knowledge Base — multi-document, semantic search, fuzzy/typo-tolerant retrieval.

Search pipeline:
  1. Text normalisation  — lowercase, collapse hyphens, strip punctuation
  2. Fuzzy expansion     — difflib finds near-matches for each query token
                           e.g. "new jrsey" → "new jersey"
  3. Semantic search     — cosine similarity on Ollama embeddings (primary)
  4. Keyword re-rank     — Jaccard boosts exact/fuzzy matches (secondary signal)
  5. Score blend         — 0.7 × semantic + 0.3 × keyword

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

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._sections:
            return []

        q_norm   = _normalise(query)
        q_tokens = _tokenize(query)
        if not q_tokens:
            return [{"section": s.section, "content": s.content, "source_file": s.source_file} for s in self._sections[:top_k]]

        # Fuzzy-expand query tokens against the vocab to fix typos
        expanded_tokens = _fuzzy_expand(q_tokens, self._vocab, cutoff=0.80)

        # ── Semantic score (primary) ──────────────────────────────────────── #
        semantic_scores: dict[int, float] = {}
        if self._store and self._semantic_ok:
            sem_results = self._store.search(query, top_k=min(top_k * 3, 20))
            # Map section content back to indices
            for res in sem_results:
                for i, s in enumerate(self._sections):
                    if s.section == res["section"] and s.content == res["content"]:
                        semantic_scores[i] = res.get("score", 0.0)
                        break

        # ── Keyword score (secondary) ─────────────────────────────────────── #
        scored: list[tuple[float, int]] = []
        for i, sec in enumerate(self._sections):
            kw_score = _jaccard(expanded_tokens, sec.tokens)
            # Heading match bonus
            if expanded_tokens & _tokenize_set(sec.section):
                kw_score *= 1.4

            sem_score = semantic_scores.get(i, 0.0)

            if self._semantic_ok and sem_score > 0:
                combined = 0.70 * sem_score + 0.30 * kw_score
            else:
                combined = kw_score  # fallback to pure keyword

            if combined > 0:
                scored.append((combined, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in scored[:top_k]:
            s = self._sections[idx]
            results.append({
                "section":     s.section,
                "content":     s.content,
                "source_file": s.source_file,
                "score":       round(score, 4),
            })
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
