"""
Loads the HR knowledge base markdown file and provides keyword-based search.

Parsing: splits the document on H1/H2/H3 headings into sections.
Search:  Jaccard similarity between query tokens and section tokens,
         with a 1.5× boost when the query matches the section heading.
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger("hr_copilot.knowledge")

# Common English stop words that add no signal for search
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "ought", "used",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "about", "over", "after", "what", "how", "when",
        "where", "who", "which", "that", "this", "these", "those", "and",
        "or", "but", "if", "then", "not", "no", "i", "my", "me", "we",
        "our", "you", "your", "it", "its", "up", "out", "so", "just",
    }
)


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


class KnowledgeSection:
    __slots__ = ("section", "content", "tokens")

    def __init__(self, section: str, content: str) -> None:
        self.section = section
        self.content = content
        self.tokens: set[str] = _tokenize(f"{section} {content}")


class KnowledgeBase:
    def __init__(self, kb_path: str) -> None:
        self._path = Path(kb_path)
        self._sections: list[KnowledgeSection] = []
        self._load()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Knowledge base not found at %s — searches will return empty results", self._path)
            return

        raw = self._path.read_text(encoding="utf-8")
        self._sections = self._parse(raw)
        logger.info("Loaded %d sections from %s", len(self._sections), self._path)

    def _parse(self, text: str) -> list[KnowledgeSection]:
        sections: list[KnowledgeSection] = []
        heading_re = re.compile(r"^#{1,3}\s+(.+)$")

        current_heading = "General"
        current_lines: list[str] = []

        def flush() -> None:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append(KnowledgeSection(current_heading, body))

        for line in text.splitlines():
            m = heading_re.match(line)
            if m:
                flush()
                current_heading = m.group(1).strip()
                current_lines = []
            else:
                stripped = line.strip()
                if stripped:
                    current_lines.append(stripped)

        flush()
        return sections

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Return up to top_k sections most relevant to *query*.
        Each result dict has: section (str), content (str).
        """
        if not self._sections:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return [{"section": s.section, "content": s.content} for s in self._sections[:top_k]]

        scored: list[tuple[float, KnowledgeSection]] = []
        for sec in self._sections:
            overlap = query_tokens & sec.tokens
            if not overlap:
                continue
            union = query_tokens | sec.tokens
            score = len(overlap) / len(union)

            # Boost sections whose heading directly contains a query term
            if query_tokens & _tokenize(sec.section):
                score *= 1.5

            scored.append((score, sec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"section": s.section, "content": s.content}
            for _, s in scored[:top_k]
        ]

    @property
    def section_count(self) -> int:
        return len(self._sections)
