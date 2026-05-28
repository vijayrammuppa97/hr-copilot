"""
Parses uploaded documents into searchable KB sections.

Supported formats:
  .pdf   — extracts text per page (requires pypdf)
  .docx  — extracts paragraphs grouped by heading (requires python-docx)
  .csv   — each row becomes a searchable entry
  .txt   — split on double newlines
  .md    — parsed on markdown headings (same as knowledge_base.md)
"""

import csv
import io
import logging
import re
from pathlib import Path

logger = logging.getLogger("hr_copilot.docs")


# ── Internal helpers ──────────────────────────────────────────────────────── #

def _chunks(text: str, filename: str, min_len: int = 40) -> list[dict]:
    """Split plain text on blank lines into sections."""
    stem = Path(filename).stem
    parts = re.split(r"\n{2,}", text.strip())
    sections = []
    for i, part in enumerate(parts):
        part = part.strip()
        if len(part) >= min_len:
            # Use the first line as the section heading
            lines = part.splitlines()
            heading = lines[0][:80] if lines else f"{stem} §{i + 1}"
            sections.append({"section": f"{stem} — {heading}", "content": part})
    return sections


def _parse_markdown(text: str, filename: str) -> list[dict]:
    """Reuse same heading-split logic as knowledge_loader."""
    stem = Path(filename).stem
    heading_re = re.compile(r"^#{1,3}\s+(.+)$")
    sections, current_heading, lines = [], f"{stem}", []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            sections.append({"section": current_heading, "content": body})

    for line in text.splitlines():
        m = heading_re.match(line)
        if m:
            flush()
            current_heading = m.group(1).strip()
            lines = []
        else:
            s = line.strip()
            if s:
                lines.append(s)
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
    sections = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if len(text) >= 40:
            sections.append({"section": f"{stem} — Page {i + 1}", "content": text})
    logger.info("Parsed %d pages from PDF %s", len(sections), filename)
    return sections


def _parse_docx(data: bytes, filename: str) -> list[dict]:
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed — run: pip install python-docx")
        return []

    stem = Path(filename).stem
    doc = Document(io.BytesIO(data))
    sections, current_heading, paras = [], stem, []

    def flush() -> None:
        body = "\n".join(paras).strip()
        if body:
            sections.append({"section": current_heading, "content": body})

    for para in doc.paragraphs:
        if para.style.name.startswith("Heading") and para.text.strip():
            flush()
            current_heading = para.text.strip()
            paras = []
        elif para.text.strip():
            paras.append(para.text.strip())

    flush()
    logger.info("Parsed %d sections from DOCX %s", len(sections), filename)
    return sections


def _parse_csv(data: bytes, filename: str) -> list[dict]:
    stem = Path(filename).stem
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    sections = []

    for i, row in enumerate(reader):
        # Build readable text from all non-empty columns
        pairs = [f"{k}: {v}" for k, v in row.items() if v and str(v).strip()]
        if not pairs:
            continue
        content = " | ".join(pairs)
        # Use first column value as a heading if available
        first_val = next(iter(row.values()), "")
        heading = str(first_val)[:60] if first_val else f"Row {i + 1}"
        sections.append({"section": f"{stem} — {heading}", "content": content})

    logger.info("Parsed %d rows from CSV %s", len(sections), filename)
    return sections


# ── Public API ────────────────────────────────────────────────────────────── #

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt", ".md", ".text"}


def parse_document(data: bytes, filename: str) -> list[dict]:
    """
    Parse an uploaded file into a list of {section, content} dicts.
    Returns empty list if the format is unsupported or parsing fails.
    """
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
        return _chunks(data.decode("utf-8", errors="replace"), filename)

    logger.warning("Unsupported file type: %s", ext)
    return []
