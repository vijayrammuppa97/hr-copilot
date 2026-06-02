"""
Parses uploaded documents into searchable KB sections using
recursive chunking with overlap.

Chunking strategy:
  - Try to split on paragraph boundaries (\n\n)
  - Fall back to sentence boundaries (. )
  - Fall back to word boundaries ( )
  - Chunk size: 400 characters | Overlap: 80 characters
  - Minimum chunk length: 60 characters

Supported formats:
  .pdf   — page-aware extraction then chunk
  .docx  — heading-grouped paragraphs then chunk
  .csv   — one row per section
  .txt   — recursive chunk
  .md    — heading-split then chunk long sections
"""

import csv
import io
import logging
import re
from pathlib import Path

logger = logging.getLogger("hr_copilot.docs")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt", ".md", ".text"}

CHUNK_SIZE    = 400   # characters
CHUNK_OVERLAP = 80    # characters
MIN_CHUNK_LEN = 60    # skip tiny fragments


# ── Recursive chunker ─────────────────────────────────────────────────────── #

def _recursive_chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks respecting natural boundaries.
    Priority order: paragraph > sentence > word boundary.
    """
    text = text.strip()
    if len(text) <= size:
        return [text] if len(text) >= MIN_CHUNK_LEN else []

    separators = ["\n\n", "\n", ". ", " "]
    chunks: list[str] = []

    def _split(block: str, depth: int = 0) -> None:
        if len(block) <= size or depth >= len(separators):
            if len(block) >= MIN_CHUNK_LEN:
                chunks.append(block.strip())
            return

        sep = separators[depth]
        parts = block.split(sep)
        current = ""
        for part in parts:
            candidate = (current + sep + part).strip() if current else part.strip()
            if len(candidate) <= size:
                current = candidate
            else:
                if current and len(current) >= MIN_CHUNK_LEN:
                    chunks.append(current.strip())
                    # Start next chunk with overlap
                    words = current.split()
                    overlap_text = " ".join(words[-max(1, overlap // 6):])
                    current = (overlap_text + sep + part).strip()
                else:
                    _split(part, depth + 1)
                    current = part.strip()
        if current and len(current) >= MIN_CHUNK_LEN:
            chunks.append(current.strip())

    _split(text)
    return chunks if chunks else [text[:size]]


def _make_sections(chunks: list[str], stem: str, base_heading: str) -> list[dict]:
    """Convert text chunks into {section, content} dicts."""
    sections = []
    for i, chunk in enumerate(chunks):
        if len(chunks) == 1:
            label = f"{stem} — {base_heading}"
        else:
            label = f"{stem} — {base_heading} (part {i + 1})"
        sections.append({"section": label, "content": chunk})
    return sections


# ── Format-specific parsers ───────────────────────────────────────────────── #

def _parse_markdown(text: str, filename: str) -> list[dict]:
    stem        = Path(filename).stem
    heading_re  = re.compile(r"^#{1,3}\s+(.+)$")
    sections: list[dict] = []
    current_heading = stem
    lines: list[str] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            for s in _make_sections(_recursive_chunk(body), stem, current_heading):
                sections.append(s)

    for line in text.splitlines():
        m = heading_re.match(line)
        if m:
            flush()
            current_heading = m.group(1).strip()
            lines = []
        else:
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    flush()
    return sections


def _parse_pdf(data: bytes, filename: str) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf not installed — run: pip install pypdf")
        return []

    stem = Path(filename).stem
    reader = PdfReader(io.BytesIO(data))
    sections: list[dict] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if len(text) < MIN_CHUNK_LEN:
            continue
        heading = f"Page {i + 1}"
        for s in _make_sections(_recursive_chunk(text), stem, heading):
            sections.append(s)
    logger.info("Parsed %d chunks from PDF %s", len(sections), filename)
    return sections


def _parse_docx(data: bytes, filename: str) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed — run: pip install python-docx")
        return []

    stem = Path(filename).stem
    doc  = Document(io.BytesIO(data))
    sections: list[dict] = []
    current_heading = stem
    paras: list[str] = []

    def flush() -> None:
        body = "\n".join(paras).strip()
        if body:
            for s in _make_sections(_recursive_chunk(body), stem, current_heading):
                sections.append(s)

    for para in doc.paragraphs:
        if para.style.name.startswith("Heading") and para.text.strip():
            flush()
            current_heading = para.text.strip()
            paras = []
        elif para.text.strip():
            paras.append(para.text.strip())
    flush()
    logger.info("Parsed %d chunks from DOCX %s", len(sections), filename)
    return sections


def _parse_csv(data: bytes, filename: str) -> list[dict]:
    stem   = Path(filename).stem
    text   = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    sections: list[dict] = []
    for i, row in enumerate(reader):
        pairs = [f"{k}: {v}" for k, v in row.items() if v and str(v).strip()]
        if not pairs:
            continue
        content    = " | ".join(pairs)
        first_val  = next(iter(row.values()), "")
        heading    = str(first_val)[:60] if first_val else f"Row {i + 1}"
        sections.append({"section": f"{stem} — {heading}", "content": content})
    logger.info("Parsed %d rows from CSV %s", len(sections), filename)
    return sections


def _parse_txt(data: bytes, filename: str) -> list[dict]:
    stem     = Path(filename).stem
    text     = data.decode("utf-8", errors="replace")
    sections: list[dict] = []
    # Split on double newlines to get paragraphs, then chunk each
    paras = re.split(r"\n{2,}", text.strip())
    for i, para in enumerate(paras):
        para = para.strip()
        if len(para) < MIN_CHUNK_LEN:
            continue
        heading = para.splitlines()[0][:80] if para.splitlines() else f"Section {i + 1}"
        for s in _make_sections(_recursive_chunk(para), stem, heading):
            sections.append(s)
    return sections


# ── Public API ────────────────────────────────────────────────────────────── #

def parse_document(data: bytes, filename: str) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(data, filename)
    if ext == ".docx":
        return _parse_docx(data, filename)
    if ext == ".csv":
        return _parse_csv(data, filename)
    if ext in {".md", ".markdown"}:
        return _parse_markdown(data.decode("utf-8", errors="replace"), filename)
    if ext in {".txt", ".text", ""}:
        return _parse_txt(data, filename)
    logger.warning("Unsupported file type: %s", ext)
    return []
