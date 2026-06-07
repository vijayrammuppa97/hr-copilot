import asyncio
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import MAX_UPLOAD_BYTES
from document_loader import parse_document, SUPPORTED_EXTENSIONS
from dependencies import get_knowledge_base

router  = APIRouter(prefix="/api", tags=["documents"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/upload")
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    sections = parse_document(data, filename)
    if not sections:
        raise HTTPException(status_code=422, detail="Could not extract content from file")
    kb    = get_knowledge_base()
    added = kb.add_sections(sections, source_file=filename)
    return {"filename": filename, "sections_added": added, "total_kb_sections": kb.section_count}


@router.get("/debug/retrieve", tags=["ops"])
async def debug_retrieve(q: str, top_k: int = 5) -> dict:
    """Return exactly which KB sections are retrieved for a query — diagnose retrieval issues."""
    kb   = get_knowledge_base()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, kb.search, q)
    return {
        "query":   q,
        "results": [
            {
                "rank":    i + 1,
                "section": r["section"],
                "score":   r.get("score", 0),
                "preview": r["content"][:300],
            }
            for i, r in enumerate(results[:top_k])
        ],
    }
