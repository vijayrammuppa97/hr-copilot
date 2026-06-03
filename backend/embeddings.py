"""
Semantic embedding store using Ollama's embedding API.

Embeddings are generated locally — no external API keys required.
Default model: nomic-embed-text (pull with: ollama pull nomic-embed-text)
Fallback model: llama3.2 (already installed)

Vector similarity: cosine similarity
Storage: in-memory list + optional SQLite cache for persistence across restarts
"""

import asyncio
import json
import logging
import math
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ollama

_executor = ThreadPoolExecutor(max_workers=2)

logger = logging.getLogger("hr_copilot.embeddings")

EMBED_MODEL  = os.getenv("EMBED_MODEL", "nomic-embed-text")
_CACHE_PATH  = Path(__file__).parent.parent / "data" / "embeddings_cache.db"


# ── Pure-Python cosine similarity ────────────────────────────────────────── #

def _cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── SQLite embedding cache ────────────────────────────────────────────────── #

def _cache_connect() -> sqlite3.Connection:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            text_hash TEXT PRIMARY KEY,
            model     TEXT NOT NULL,
            vector    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _cache_get(text_hash: str, model: str) -> list[float] | None:
    try:
        conn = _cache_connect()
        row = conn.execute(
            "SELECT vector FROM embedding_cache WHERE text_hash = ? AND model = ?",
            (text_hash, model),
        ).fetchone()
        return json.loads(row["vector"]) if row else None
    except Exception:
        return None


def _cache_set(text_hash: str, model: str, vector: list[float]) -> None:
    try:
        conn = _cache_connect()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "INSERT OR REPLACE INTO embedding_cache (text_hash, model, vector, created_at) VALUES (?, ?, ?, ?)",
            (text_hash, model, json.dumps(vector), now),
        )
        conn.commit()
    except Exception:
        pass


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


# ── Embedding generator ───────────────────────────────────────────────────── #

class EmbeddingGenerator:
    def __init__(self, model: str = EMBED_MODEL, host: str = "http://localhost:11434") -> None:
        self._model  = model
        self._client = ollama.Client(host=host)
        self._verify_model()

    def _verify_model(self) -> None:
        try:
            self._client.embeddings(model=self._model, prompt="test")
            logger.info("Embedding model ready: %s", self._model)
        except Exception as exc:
            # Fall back to llama3.2 which is always available
            logger.warning("Embed model %s unavailable (%s) — falling back to llama3.2", self._model, exc)
            self._model = "llama3.2"

    def embed(self, text: str, use_cache: bool = True) -> list[float]:
        text = text.strip()
        h = _hash_text(f"{self._model}:{text}")
        if use_cache:
            cached = _cache_get(h, self._model)
            if cached:
                return cached
        try:
            # keep_alive=-1 keeps the embedding model in Ollama's memory
            # so llama3.2 can also stay loaded simultaneously
            resp   = self._client.embeddings(model=self._model, prompt=text, keep_alive=-1)
            vector = resp["embedding"]
            if use_cache:
                _cache_set(h, self._model, vector)
            return vector
        except Exception as exc:
            logger.error("Embedding failed for text='%s...': %s", text[:40], exc)
            return []

    async def embed_async(self, text: str, use_cache: bool = True) -> list[float]:
        """Non-blocking wrapper — runs embed() in a thread so the event loop stays free."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.embed, text, use_cache)

    @property
    def model(self) -> str:
        return self._model


# ── In-memory vector store ────────────────────────────────────────────────── #

class VectorStore:
    """
    Holds embedded document sections in memory.
    Supports cosine-similarity search + optional keyword re-ranking.
    """

    def __init__(self, generator: EmbeddingGenerator) -> None:
        self._gen      = generator
        self._vectors: list[list[float]] = []
        self._sections: list[dict]       = []   # {section, content, source_file}

    def add(self, section: str, content: str, source_file: str = "") -> None:
        text   = f"{section}\n{content}"
        vector = self._gen.embed(text)
        if vector:
            self._vectors.append(vector)
            self._sections.append({"section": section, "content": content, "source_file": source_file})

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._vectors:
            return []
        q_vec = self._gen.embed(query)
        if not q_vec:
            return []
        scored = [
            (_cosine(q_vec, v), i)
            for i, v in enumerate(self._vectors)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in scored[:top_k]:
            entry = dict(self._sections[idx])
            entry["score"] = round(score, 4)
            results.append(entry)
        return results

    def clear(self) -> None:
        self._vectors.clear()
        self._sections.clear()

    @property
    def count(self) -> int:
        return len(self._sections)
