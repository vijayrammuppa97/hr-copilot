# HR Knowledge Copilot

An AI-powered enterprise HR assistant that answers employee questions about company policies using a fully local stack — no API keys, no cloud services. Built with React + TypeScript on the frontend and FastAPI + Python on the backend, powered by Ollama.

---

## Project Overview

Employees ask natural-language HR questions ("How many sick days do I get?", "Can I work from abroad?", "Can I carry forward unused leave?") and receive accurate, cited answers grounded in the company's HR policy document.

**Key features:**
- Hybrid RAG pipeline: BM25 keyword search + bge-m3 semantic embeddings + RRF fusion
- Query rewriting with synonym expansion and typo tolerance (fuzzy matching)
- Cross-encoder reranker for precision after retrieval
- **Personal context awareness** — LLM applies the user's tenure, role, and employment type to calculate their specific entitlement from policy tables (e.g. "I've worked here 3 years" → calculates the exact leave tier)
- **Guaranteed section injection** — critical reference sections (tenure table, WFH days table) are always added to context when relevant, even if retrieval misses them
- Strict evidence-based answers — LLM must cite the exact policy section used
- Confidence score and policy section citations on every response
- Conversation history (last 6 turns) for follow-up questions
- Multi-document knowledge base — drop files into `data/knowledge_docs/` and they auto-index
- Live document watcher — no restart needed when KB files change
- Admin dashboard with usage stats, evaluation metrics, confidence distribution
- User identity + session history tree
- Onboarding case management with workflow stages
- Rate limiting (20 chat requests/minute per IP)
- 100% local — llama3.2 + bge-m3 run via Ollama on your machine

---

## Architecture

```
Browser (port 3000)
        │
        │  POST /api/chat  (Vite proxy → 127.0.0.1:8080)
        ▼
FastAPI Backend (port 8080)
        │
        ├── query_rewriter.py   ← synonym expansion, fuzzy expansion, typo correction
        │
        ├── knowledge_loader.py ← hybrid search orchestrator
        │       ├── bm25_index.py     ← BM25 keyword search (top 20)
        │       ├── embeddings.py     ← bge-m3 semantic search (top 20)
        │       ├── RRF fusion        ← combines both ranked lists
        │       ├── policy boosts     ← 3× title boost, 2× content boost
        │       └── reranker.py       ← CrossEncoder rerank → top 8 chunks
        │
        ├── llm_handler.py      ← llama3.2 via Ollama, streaming, num_ctx=8192
        │
        ├── database.py         ← SQLite: conversations, feedback, evaluation logs
        ├── user_manager.py     ← user identity, session history
        ├── case_manager.py     ← onboarding workflow cases
        ├── evaluation.py       ← Recall@K, faithfulness, relevance scoring
        └── document_watcher.py ← watchdog on data/knowledge_docs/

Data flow (single chat request):
1. Query rewriter expands synonyms and typo-corrects the user message
2. BM25 index searches top-20 keyword matches
3. bge-m3 semantic search retrieves top-20 vector matches
4. RRF fusion merges both ranked lists
5. Policy title boost (3×) + content keyword boost (2×) applied
6. Guaranteed section injection — tenure table, WFH days table, sick leave policy added when relevant
7. Reranker selects final top-8 chunks
8. llama3.2 applies user's personal context (tenure, role) to calculate specific entitlements
9. Response streamed token-by-token via SSE to the frontend
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend dev server |
| npm | 9+ | Frontend package manager |
| Ollama | 0.2+ | Local LLM + embedding server |

> No Anthropic or OpenAI API key required. Everything runs locally.

---

## Ollama Setup

Install Ollama from [ollama.com](https://ollama.com), then pull the two models:

```bash
# Language model (LLM)
ollama pull llama3.2

# Embedding model
ollama pull bge-m3
```

Start the Ollama server (runs in background):
```bash
ollama serve
```

Verify:
```bash
ollama list
# Should show: llama3.2, bge-m3
```

---

## Running the Application

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Verify:
```bash
curl http://localhost:8080/health
# → {"status":"healthy","model":"llama3.2","embed_model":"bge-m3","kb_sections":63,...}
```

### Frontend

Open a new terminal:

```bash
cd frontend
npm install        # first time only
npm run dev
```

App opens at **http://localhost:3000**

The Vite proxy forwards all `/api/*` requests to `http://127.0.0.1:8080` (note: must be `127.0.0.1`, not `localhost`, to avoid IPv6 resolution issues).

---

## Environment Variables

`backend/.env`:

```env
OLLAMA_MODEL=llama3.2
OLLAMA_HOST=http://localhost:11434
EMBED_MODEL=bge-m3
ADMIN_TOKEN=hr-admin-secret-2024
QUERY_REWRITE_LLM=false
KB_PATH=../data/knowledge_base.md
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `llama3.2` | Chat LLM served by Ollama |
| `EMBED_MODEL` | `bge-m3` | Embedding model for semantic search |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `ADMIN_TOKEN` | `hr-admin-secret-2024` | Bearer token for admin endpoints |
| `QUERY_REWRITE_LLM` | `false` | Use LLM for query rewriting (slower, not recommended) |
| `KB_PATH` | `../data/knowledge_base.md` | Primary HR policy document |

---

## Project Structure

```
hr-copilot-final/
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Chat state, SSE streaming, session mgmt
│   │   ├── components/
│   │   │   ├── ChatMessage.tsx      # Message bubble, sources, confidence badge
│   │   │   ├── ChatInput.tsx        # Textarea, submit, file upload
│   │   │   ├── Sidebar.tsx          # Nav, onboarding checklist, session history
│   │   │   ├── AdminDashboard.tsx   # Usage stats, evaluation charts
│   │   │   ├── WorkflowProgress.tsx # Onboarding stage tracker
│   │   │   └── EscalationModal.tsx  # HR escalation form
│   │   └── types/index.ts
│   └── vite.config.ts               # Proxy: /api → 127.0.0.1:8080
│
├── backend/
│   ├── main.py               # FastAPI app, routing, CORS, rate limiting
│   ├── knowledge_loader.py   # Hybrid RAG orchestrator (BM25 + semantic + RRF + guaranteed injection)
│   ├── bm25_index.py         # BM25 keyword index (rank-bm25)
│   ├── embeddings.py         # bge-m3 embedding generator + SQLite vector cache
│   ├── reranker.py           # CrossEncoder / Ollama reranker
│   ├── query_rewriter.py     # Synonym expansion, fuzzy correction
│   ├── llm_handler.py        # Ollama streaming chat, grounding prompt
│   ├── document_loader.py    # PDF, DOCX, CSV, MD parser
│   ├── document_watcher.py   # Live file watcher for knowledge_docs/
│   ├── database.py           # SQLite: conversations, feedback, eval logs
│   ├── user_manager.py       # User identity + session tree
│   ├── case_manager.py       # Onboarding workflow case management
│   ├── evaluation.py         # Recall@K, faithfulness, relevance scoring
│   └── .env                  # Local config (not committed)
│
└── data/
    ├── knowledge_base.md      # Primary HR policy (63 sections)
    ├── knowledge_docs/        # Drop additional docs here — auto-indexed on start
    ├── embeddings_cache.db    # SQLite vector cache (bge-m3 embeddings)
    └── hr_copilot.db          # SQLite app database
```

---

## Retrieval Pipeline

Every query goes through this pipeline:

```
User Query
    │
    ▼
Query Rewriter
  • Abbreviation expansion  (PTO → annual leave entitlement accrues calendar year)
  • Synonym expansion       (new dad → paternity leave non-birthing parent)
  • Synonym expansion       (vacation rollover → carry-forward annual leave roll over)
  • Fuzzy typo correction   (matarnity → maternity)
    │
    ▼
Hybrid Search (runs in parallel)
  ├── BM25        → top 20 keyword matches
  └── bge-m3      → top 20 semantic matches
    │
    ▼
RRF Fusion        → merges both ranked lists
    │
    ▼
Boosting
  ├── Policy title boost  3.0× (query term matches section heading)
  └── Content boost       2.0× (discriminating KB-specific terms found)
    │
    ▼
Guaranteed Section Injection
  • Tenure mentioned?        → always inject 1.2 Annual Leave Days by Tenure
  • Mental health query?     → always inject 1.6 Sick Leave Policy
  • Remote work + days?      → always inject 2.3 Remote Work Days Allowed Per Week
  • Eligibility for WFH?     → always inject 2.3 Remote Work Days Allowed Per Week
    │
    ▼
Reranker          → CrossEncoder or Ollama rerank → top 8 chunks
    │
    ▼
llama3.2
  • Reads user's personal context (tenure, role, employment type)
  • Applies policy tables to calculate specific entitlement
  • Must cite section(s) used
    │
    ▼
Streamed answer via SSE
```

**Retrieval accuracy benchmark (22/24 test queries correct):**

| Query variant | Correct section retrieved |
|---|---|
| vacation rollover | 1.4 Annual Leave Carry-Forward Rules |
| new dad leave | 1.10 Paternity Leave |
| flu day off | 1.6 Sick Leave Policy |
| pregnancy leave | 1.9 Maternity Leave |
| laptop stolen what to do | 2.6.1 Lost or Stolen Equipment |
| raise a complaint | 5.4 Formal Grievance Procedure |
| death in family time off | Bereavement Leave |
| court attendance work | Jury Duty and Civic Leave |

---

## API Reference

### `POST /api/chat`
Stream an SSE response to a user HR question.

**Request:**
```json
{
  "message": "How many sick days do I get?",
  "conversationId": "user-abc-123",
  "userId": "optional-user-id",
  "caseId": "optional-case-id"
}
```

**Response:** Server-Sent Events stream
```
data: {"type": "token", "text": "You"}
data: {"type": "token", "text": " receive"}
...
data: {"type": "done", "sources": ["1.6 Sick Leave Policy"], "confidence": 0.82, "timestamp": "..."}
```

### `GET /api/debug/retrieve?q=<query>&top_k=5`
Show exactly which chunks are retrieved for a query — use this to diagnose retrieval failures before blaming the LLM.

```bash
curl "http://localhost:8080/api/debug/retrieve?q=paternity+leave"
```

### `GET /health`
Returns server status, loaded model names, KB section count, and semantic/BM25 availability.

### `POST /api/upload`
Upload a PDF, DOCX, CSV, TXT, or Markdown file to add to the knowledge base at runtime.

### `POST /api/cases`
Create an onboarding case for a new employee.

### `GET /api/admin/stats` *(requires `Authorization: Bearer <ADMIN_TOKEN>`)*
Returns total messages, unique users, avg confidence, top queries, eval metrics.

---

## Adding Knowledge Documents

Drop any supported file into `data/knowledge_docs/`:

```
data/knowledge_docs/
├── benefits_2025.pdf
├── expense_policy.docx
└── remote_work_addendum.md
```

The document watcher re-indexes changed files automatically (30-second polling, or real-time with `pip install watchdog`). Supported formats: `.pdf`, `.docx`, `.csv`, `.txt`, `.md`.

---

## Example Queries to Test

**With personal context (LLM calculates your specific entitlement):**
- "I am working since 3 years at Acme, how many annual leave days do I get?"
  → Looks up 2–5 year tier → answers "18 days"
- "I have been here 1 year, how many days can I work from home?"
  → Confirms eligibility (3-month minimum met) → answers "up to 3 days/week (standard hybrid)"
- "I've worked here 3 years, how many mental health days will I get?"
  → Answers "2 days" and explains they come from your 10-day sick leave balance

**Leave policy:**
- "Can I carry forward unused vacation days?" / "vacation rollover"
- "What are the paternity leave rules for new dads?"
- "How long is maternity leave and is it paid?"
- "Do I need a doctor's note for 2 sick days?"
- "I had a bereavement — how many days off can I take?"

**Remote work:**
- "Who is eligible to work from home?"
- "How many WFH days per week am I allowed?"
- "My laptop was stolen — what do I do?"
- "Can I work from another country?"

**HR process:**
- "How do I raise a formal grievance?"
- "What happens during a disciplinary process?"
- "How long does HR have to acknowledge my complaint?"

**Irrelevant (correctly deflected):**
- "What is the capital of France?"
→ "I could not find that information in our HR policy. Please contact HR at hr@company.com."

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No response in chat | Vite proxy not reaching backend | Ensure backend is on port 8080; vite.config.ts must proxy to `127.0.0.1:8080` not `localhost:8080` |
| `bge-m3` unavailable on startup | Model not pulled | Run `ollama pull bge-m3` |
| `rank-bm25 not installed` in logs | Package missing from venv | Run `.venv/Scripts/python.exe -m pip install rank-bm25` |
| Slow first response (~30s) | Models loading into RAM | First request cold-starts the models; subsequent requests are fast |
| `kb_sections: 0` in health | Wrong KB_PATH | Check `KB_PATH` in `backend/.env` is relative to where uvicorn runs |
| Frontend shows "Failed to fetch" | Backend not running | Start uvicorn on port 8080 |
| Chat hangs forever | Ollama not running | Run `ollama serve` in a separate terminal |
| LLM ignores user's years of service | Tenure table not in retrieval | Guaranteed injection handles this — ensure `_TENURE_RE` pattern matches the phrasing |
| LLM says "no specific policy for WFH days" | Section 2.3 not retrieved | Guaranteed injection for remote+days queries; check `_GUARANTEED_SECTIONS` in `knowledge_loader.py` |

---

## Hardware Notes

This stack runs fully on CPU. Tested on:

| Component | Spec |
|-----------|------|
| CPU | Intel Core i7-1255U (10 cores) |
| RAM | 16 GB |
| GPU | Intel Iris Xe 2 GB (integrated — not used for inference) |
| Avg retrieval latency | ~2.8s (bge-m3 CPU embedding) |
| Avg LLM response | ~10–15s (llama3.2 on CPU) |

For faster responses, a dedicated NVIDIA GPU with 8 GB+ VRAM would run both models on GPU via Ollama's CUDA backend.

---

## License

Internal use only. Not for public distribution.
