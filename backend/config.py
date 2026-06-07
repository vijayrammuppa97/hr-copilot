"""
Central configuration — all environment variables loaded here.
Every other module imports from this file instead of calling os.getenv directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",  "llama3.2")
OLLAMA_HOST   = os.getenv("OLLAMA_HOST",   "http://localhost:11434")
EMBED_MODEL   = os.getenv("EMBED_MODEL",   "bge-m3")
KB_PATH       = os.getenv("KB_PATH",       "../data/knowledge_base.md")
ADMIN_TOKEN   = os.getenv("ADMIN_TOKEN",   "hr-admin-secret-2024")
CORS_ORIGINS  = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]
MAX_HISTORY_ENTRIES = 12
MAX_UPLOAD_BYTES    = 10 * 1024 * 1024   # 10 MB
