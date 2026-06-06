"""
HR Knowledge Base — Hybrid RAG pipeline.

Full pipeline (per query):
  User Query
      ↓
  Query Rewriter  (query_rewriter.py)
      ↓
  Hybrid Search
      ├── BM25      (bm25_index.py)     — keyword precision
      └── Semantic  (embeddings.py)     — meaning recall
      ↓
  RRF Fusion  — Reciprocal Rank Fusion combines both ranked lists
      ↓
  Reranker    (reranker.py)            — CrossEncoder > Ollama > ScoreFusion
      ↓
  Top-K Chunks  → LLM

Additional signals:
  - Policy keyword boost (2.5×) — known HR section names
  - Content keyword boost (2.0×) — critical terms in chunk text
  - Fuzzy query expansion        — handles typos via difflib
  - Similarity threshold         — drops noise below 0.12
  - Per-query chunk logging      — every retrieved section logged

Admin folder:
  Files in data/knowledge_docs/ are indexed on startup and watched for changes.
"""

import difflib
import logging
import re
from pathlib import Path

# Patterns that indicate the user is providing personal tenure/context
_TENURE_RE = re.compile(
    r"\b(\d+)\s*(year|yr|month|day)s?\b"
    r"|working\s+since|been\s+here|joined|years?\s+of\s+service"
    r"|experience|tenure|employed\s+for",
    re.IGNORECASE,
)

# Section title fragments that must always be included when certain topics are detected
_GUARANTEED_SECTIONS: list[tuple[re.Pattern, str]] = [
    # Tenure mentioned → always include the tenure entitlement table
    (_TENURE_RE,
     "Annual Leave Days by Tenure"),
    # Mental health query → include sick leave policy (MH days come from sick balance)
    (re.compile(r"mental\s+health|wellbeing|burnout", re.IGNORECASE),
     "Sick Leave Policy"),
    # Sick leave queries → include the sick leave policy
    (re.compile(r"sick|ill|medical|doctor",           re.IGNORECASE),
     "Sick Leave Policy"),
    # Remote work + days/how many → always include section 2.3 (the actual days-per-week table)
    (re.compile(r"(how\s+many|days?|per\s+week).{0,30}(remote|wfh|work\s+from\s+home)"
                r"|(remote|wfh|work\s+from\s+home).{0,30}(how\s+many|days?|per\s+week)",
                re.IGNORECASE),
     "Remote Work Days Allowed"),
    # Eligibility for remote → also include days table so LLM can give complete picture
    (re.compile(r"eligib|can\s+i\s+work\s+from\s+home|allowed\s+to\s+work\s+remote",
                re.IGNORECASE),
     "Remote Work Days Allowed"),
]

from embeddings import EmbeddingGenerator, VectorStore
from bm25_index import BM25Index
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
SIMILARITY_THRESHOLD = 0.12   # permissive enough to catch short policy sentences

# Policy section keyword map — when a query mentions these terms,
# chunks whose headings contain the matched keywords receive a 2.5× boost.
# This directly fixes the "paternity leave → Jury Duty" class of errors.
_POLICY_KEYWORDS: dict[str, list[str]] = {
    "annual leave":        ["annual", "leave", "vacation", "holiday", "pto", "paid time off",
                            "time off", "days off", "vacation days", "annual leave"],
    "sick leave":          ["sick", "medical", "illness", "doctor", "certificate", "flu",
                            "cold", "unwell", "sick day", "call in sick", "off sick"],
    "paternity leave":     ["paternity", "father", "paternal", "dad", "new dad",
                            "non-birthing", "secondary caregiver", "birth of child",
                            "newborn", "birth registration"],
    "maternity leave":     ["maternity", "mother", "maternal", "pregnancy", "pregnant",
                            "birthing", "expecting", "due date", "prenatal", "birth parent",
                            "birthing parent"],
    "parental leave":      ["parental", "parent", "shared parental"],
    "adoption leave":      ["adoption", "adopt", "adoptive", "adopting", "adopted",
                            "child placement"],
    "remote work":         ["remote", "wfh", "work from home", "hybrid", "work remotely",
                            "home office", "days per week", "work remotely", "remote days"],
    "grievance":           ["grievance", "complaint", "formal", "dispute", "raise a concern",
                            "formal complaint"],
    "performance":         ["performance", "review", "appraisal", "pip"],
    "resignation":         ["resign", "notice", "termination", "leaving", "quit"],
    "expense":             ["expense", "reimbursement", "claim", "receipt", "reimburse"],
    "equipment":           ["equipment", "laptop", "device", "hardware", "stolen", "lost",
                            "company equipment"],
    "harassment":          ["harassment", "bully", "posh", "misconduct", "bullying"],
    "carry forward":       ["carry", "carryover", "rollover", "unused leave", "roll over",
                            "vacation rollover", "unused days", "leave balance"],
    "emergency leave":     ["emergency", "bereavement", "compassionate", "funeral", "death",
                            "grief", "family death", "passed away", "condolence"],
    "jury duty":           ["jury", "civic", "court", "witness", "jury service",
                            "court attendance", "jury summons", "civic duty"],
    "training":            ["training", "learning", "development", "course", "lms"],
    "payroll":             ["payroll", "salary", "pay", "bank", "tax", "deduction"],
    "onboarding":          ["onboarding", "joining", "induction", "first day"],
}


def _content_keyword_boost(query_tokens: set[str], content: str) -> float:
    """
    Direct content-level boost for queries that contain high-signal terms
    which also appear in the chunk content.
    Handles cases like stolen-laptop where the key sentence is a short paragraph
    that would otherwise score too low on title matching alone.
    """
    content_lower = content.lower()
    # High-signal term pairs: if query has term_a AND content has term_b, boost
    signal_pairs = [
        # Equipment — specific to 2.6.1
        ({"stolen", "theft", "missing", "lost"}, {"it security", "4 hours", "report"}),
        # Annual leave — use "pre-approved" / "calendar year" as discriminators
        # Exclude "vacation" to avoid boosting 1.1 over 1.4 for "vacation rollover" queries
        ({"pto", "paid time off", "days off", "how many days", "days per year"},
         {"entitlement", "calendar year", "accrues", "pre-approved"}),
        # Sick leave — specific to 1.6/1.7 (not mental health)
        ({"sick", "illness", "medical", "flu", "cold", "unwell", "sick day"},
         {"consecutive", "documentation", "certificate", "sick leave"}),
        # Paternity — "non-birthing" and "secondary caregiver" are ONLY in 1.10
        # Do NOT include "paternity" in content_set — section 1.12 also mentions it
        ({"paternity", "father", "dad", "new dad", "non-birthing"},
         {"non-birthing", "secondary caregiver"}),
        # Maternity — use "birthing" / "due date" as discriminator (only in 1.9)
        ({"maternity", "pregnancy", "pregnant", "expecting", "birthing"},
         {"birthing", "due date", "pre-natal", "post-natal"}),
        # Carry-forward — use "roll over" / "carry-forward" as discriminator (only in 1.4)
        ({"rollover", "roll over", "vacation rollover", "carryover", "carry forward", "unused"},
         {"carry-forward", "roll over", "forfeited", "december 31"}),
        # Grievance
        ({"grievance", "complaint", "dispute", "formal complaint"},
         {"acknowledgement", "investigation", "working days"}),
        # Remote work
        ({"remote", "wfh", "work from home", "work remotely"},
         {"eligible", "hybrid", "home office"}),
        # Bereavement — specific to 1.13 (only section with "immediate family")
        ({"bereavement", "death", "funeral", "grief", "family death", "passed away"},
         {"immediate family", "bereavement", "obituary"}),
    ]
    for query_set, content_set in signal_pairs:
        if any(q in " ".join(query_tokens) for q in query_set):
            if any(c in content_lower for c in content_set):
                return 2.0   # strong boost for content-matched policy chunks
    return 1.0


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
            return 3.0
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


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────── #

def _rrf_fusion(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Combine multiple ranked lists into one using Reciprocal Rank Fusion.
    RRF score for doc d = Σ_i  1 / (k + rank_i(d))

    Advantages over score normalisation:
    - Robust to different score scales across BM25 and cosine
    - Doesn't require calibrated scores
    - Consistently outperforms linear score combination in IR benchmarks
    """
    rrf_scores: dict[str, float] = {}
    doc_store:  dict[str, dict]  = {}

    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            key = f"{doc['section']}|||{doc['content'][:80]}"
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_store[key]  = doc

    sorted_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    return [{**doc_store[k], "rrf_score": round(rrf_scores[k], 6)} for k in sorted_keys]


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

        # BM25 keyword index
        self._bm25 = BM25Index()

        # Semantic vector store (may be unavailable if Ollama is down at startup)
        try:
            self._gen   = EmbeddingGenerator(host=embed_host)
            self._store = VectorStore(self._gen)
            self._semantic_ok = True
        except Exception as exc:
            logger.warning("Embedding store unavailable — falling back to BM25 only: %s", exc)
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
        self._rebuild_bm25()
        logger.info(
            "KnowledgeBase ready — %d sections, %d vocab tokens, semantic=%s, bm25=%s",
            len(self._sections), len(self._vocab), self._semantic_ok, self._bm25.doc_count > 0,
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

    def _rebuild_bm25(self) -> None:
        self._bm25.build([
            {"section": s.section, "content": s.content, "source_file": s.source_file}
            for s in self._sections
        ])

    # ── Search ────────────────────────────────────────────────────────────── #

    def search(self, query: str, top_k: int = 8, extra_queries: list[str] | None = None) -> list[dict]:
        """
        Retrieve the top_k most relevant sections for a query.

        Hybrid pipeline:
          1. Fuzzy-expand query tokens (typo tolerance)
          2. BM25 keyword search on primary query + all extra_queries
          3. Semantic search on primary query + all extra_queries
          4. RRF fusion of all BM25 + semantic ranked lists
          5. Policy title + content keyword boosts applied post-fusion
          6. Similarity threshold filter
          7. Log all retrieved chunks
        """
        if not self._sections:
            return []

        all_queries = [query] + (extra_queries or [])
        q_tokens    = _tokenize(query)
        if not q_tokens:
            return [
                {"section": s.section, "content": s.content, "source_file": s.source_file, "score": 0.0}
                for s in self._sections[:top_k]
            ]

        # 1. Fuzzy-expand for typo tolerance
        expanded_tokens = _fuzzy_expand(q_tokens, self._vocab, cutoff=0.80)

        # 2 + 3. BM25 + Semantic for all query variants
        all_rankings: list[list[dict]] = []

        # BM25 for each query
        for q in all_queries:
            bm25_results = self._bm25.search(q, top_k=20)
            if bm25_results:
                all_rankings.append(bm25_results)

        # Semantic for each query
        if self._store and self._semantic_ok:
            for q in all_queries:
                sem_results = self._store.search(q, top_k=20)
                if sem_results:
                    all_rankings.append(sem_results)

        # 4. RRF fusion
        if all_rankings:
            fused = _rrf_fusion(all_rankings)
        else:
            # Fallback: pure Jaccard if both BM25 and semantic unavailable
            scored_fb: list[tuple[float, int]] = []
            for i, sec in enumerate(self._sections):
                sc = _jaccard(expanded_tokens, sec.tokens)
                if sc > 0:
                    scored_fb.append((sc, i))
            scored_fb.sort(reverse=True)
            fused = [
                {"section": self._sections[i].section, "content": self._sections[i].content,
                 "source_file": self._sections[i].source_file, "score": round(s, 4), "rrf_score": round(s, 4)}
                for s, i in scored_fb[:top_k * 2]
            ]

        # 5. Apply policy + content boosts to the fused list
        boosted: list[tuple[float, dict]] = []
        for doc in fused:
            base   = doc.get("rrf_score", doc.get("score", 0.0))
            pb     = _policy_title_boost(expanded_tokens, doc["section"])
            cb     = _content_keyword_boost(expanded_tokens, doc["content"])
            # Multiplicative when both fire — compounds signal (e.g. 3.0 × 2.0 = 6.0×)
            boost  = pb * cb if pb > 1.0 and cb > 1.0 else max(pb, cb)
            final  = base * boost if boost > 1.0 else base
            d      = dict(doc)
            d["score"] = round(final, 4)
            boosted.append((final, d))

        boosted.sort(key=lambda x: x[0], reverse=True)

        # 6. Threshold filter (always keep at least 3)
        results: list[dict] = []
        for score, doc in boosted[:top_k * 2]:
            if score < SIMILARITY_THRESHOLD and len(results) >= 3:
                break
            results.append(doc)
            if len(results) >= top_k:
                break

        # 7. Guaranteed section injection
        # When queries mention tenure or specific topics, ensure the relevant
        # reference sections are always in context even if retrieval missed them.
        existing_titles = {r["section"].lower() for r in results}
        for pattern, required_fragment in _GUARANTEED_SECTIONS:
            if pattern.search(query) and not any(required_fragment.lower() in t for t in existing_titles):
                match = next(
                    (s for s in self._sections if required_fragment.lower() in s.section.lower()),
                    None,
                )
                if match:
                    results.append({
                        "section":     match.section,
                        "content":     match.content,
                        "source_file": match.source_file,
                        "score":       0.0,
                    })
                    existing_titles.add(match.section.lower())
                    logger.info("GUARANTEED section injected: %r", match.section)

        # 8. Log for diagnosis
        logger.info(
            "RETRIEVE query=%r variants=%d top=%d",
            query[:60], len(all_queries), len(results),
        )
        for rank, r in enumerate(results, 1):
            logger.info(
                "  [%d] score=%.4f  section=%r  preview=%r",
                rank, r["score"], r["section"], r["content"][:100],
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
