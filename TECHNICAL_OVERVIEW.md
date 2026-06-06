# HR Knowledge Copilot — Technical Overview

**Version 5.0 | Stack: FastAPI + React + Ollama (local LLM)**

---

## 1. Backend API — Request / Response Contracts

The backend is a **FastAPI** application (`backend/main.py`) running on port **8080**. All endpoints use JSON bodies with Pydantic validation. The chat endpoint streams via **Server-Sent Events (SSE)**.

### 1.1 Core Endpoints

#### `POST /api/chat`
The primary endpoint. Accepts a user message and returns a streamed AI response.

**Request body:**
```json
{
  "message":        "How many annual leave days do I get after 3 years?",
  "conversationId": "user-abc-1749123456-xyz",
  "userId":         "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "caseId":         "case-001"
}
```

| Field | Type | Required | Constraint |
|---|---|---|---|
| `message` | string | Yes | 1–2000 chars, stripped |
| `conversationId` | string | Yes | 1–100 chars |
| `userId` | string | No | Links to stored user profile |
| `caseId` | string | No | Scopes answer to onboarding stage |

**Response — SSE stream:**
```
data: {"type": "token",  "text": "You"}
data: {"type": "token",  "text": " are entitled to"}
data: {"type": "token",  "text": " 18 days"}
...
data: {
  "type":                "done",
  "sources":             ["1.2 Annual Leave Days by Tenure", "1.1 Annual Leave Overview"],
  "confidence":          0.82,
  "follow_up_questions": ["How do I apply for annual leave?", "Can I carry forward unused leave?"],
  "eval":                {"recall_at_k": 1.0, "faithfulness": 0.94, "relevance_score": 0.82, "k": 3},
  "timestamp":           "2025-06-03T18:30:00Z"
}
```

**Error events (within the stream):**
```
data: {"type": "error", "message": "Could not reach Ollama. Make sure it is running: ollama serve"}
```

**HTTP error responses:**
| Status | Condition |
|---|---|
| `400` | Invalid body (missing field, blank message, exceeds max length) |
| `422` | Pydantic validation failure |
| `429` | Rate limit exceeded (20 chat requests/minute per IP) |
| `500` | Unhandled exception (logged server-side) |

---

#### `GET /health`
Returns current system status. Use this before making chat requests to verify readiness.

**Response:**
```json
{
  "status":           "healthy",
  "model":            "llama3.2",
  "embed_model":      "bge-m3",
  "kb_sections":      63,
  "kb_sources":       ["knowledge_base.md"],
  "semantic_enabled": true,
  "timestamp":        "2025-06-03T18:30:00Z"
}
```

---

#### `GET /api/debug/retrieve?q=<query>&top_k=5`
Returns exactly which KB sections were retrieved for a query, with scores.
Intended for developers diagnosing retrieval failures.

**Response:**
```json
{
  "query": "paternity leave",
  "results": [
    {"rank": 1, "section": "1.10 Paternity Leave", "score": 0.082, "preview": "Non-birthing parents..."},
    {"rank": 2, "section": "1.11 Shared Parental Leave", "score": 0.064, "preview": "Following the first..."}
  ]
}
```

---

#### `PATCH /api/users/{user_id}/profile`
Updates stored user profile attributes (tenure, role, department, employment type).
Profile is silently injected into every subsequent LLM call.

**Request body:**
```json
{
  "tenure_years":    3.0,
  "employment_type": "full-time",
  "department":      "Engineering",
  "role":            "Senior Engineer"
}
```

---

#### `POST /api/upload`
Upload a document to extend the knowledge base at runtime. No restart required.

| Constraint | Value |
|---|---|
| Max file size | 10 MB |
| Supported formats | `.pdf`, `.docx`, `.csv`, `.txt`, `.md` |
| Rate limit | 5 uploads/minute |

---

#### `POST /api/feedback`
Record user feedback on an AI response (thumbs up / down).

```json
{
  "messageId":      "msg-xyz",
  "conversationId": "conv-abc",
  "feedback":       "helpful"
}
```

---

### 1.2 Context Management

Conversation context is managed per `conversationId` using the **SQLite `messages` table**:

- History is loaded from the database on every request (`get_history_from_db(cid, limit=12)`)
- Last 12 turns (6 user + 6 assistant) passed to the LLM as the `messages` array
- Persists across server restarts — no in-memory state
- `userId` links to a stored profile (`tenure_years`, `employment_type`, `department`, `role`) that is silently prepended to every message

**Context priority order passed to LLM:**
1. System prompt (grounding rules + case context if onboarding)
2. Conversation history (last 12 turns from DB)
3. User profile prefix `[Employee profile: 3 years of service, full-time, Engineering]`
4. Retrieved KB sections in `<policy_context>` XML block
5. User message

---

## 2. LLM Integration — Latency, Failures, and Conversation Context

### 2.1 Model Configuration

| Parameter | Value | Reason |
|---|---|---|
| Model | `llama3.2` (via Ollama) | Local, no API key, data stays on-premise |
| Embedding model | `bge-m3` (via Ollama) | Best-in-class open retrieval embeddings |
| Temperature | `0.05` | Near-deterministic — prevents creative hallucination |
| `num_ctx` | `8192` | Large context window for multi-section policy docs |
| `num_predict` | `400` | Caps response length, prevents rambling |
| `repeat_penalty` | `1.1` | Reduces repetitive policy quoting |
| `keep_alive` | `-1` | Models stay loaded in Ollama RAM between requests |

### 2.2 Latency Handling

**Token streaming (SSE):** The user sees the first token within ~2 seconds on CPU, rather than waiting 15 seconds for the full response. This is the primary latency mitigation.

**Embedding cache:** `bge-m3` embeddings are cached in SQLite (`data/embeddings_cache.db`) keyed by `SHA-256(text) + model_name`. On server restart with a warm cache, KB indexing takes ~2s instead of ~60s.

**Retrieval async:** The KB search runs in a thread pool (`loop.run_in_executor`) so it does not block the FastAPI async event loop during the 2–3s bge-m3 embedding call.

**Frontend timeout:** `AbortSignal.timeout(125_000)` — 125-second hard timeout on the frontend fetch. Surfaces as a clear "request timed out" message with retry.

**Hardware baseline (tested):**

| Stage | Latency |
|---|---|
| Query rewriting + BM25 search | < 50ms |
| bge-m3 semantic embedding (CPU) | ~2.5s |
| RRF fusion + boosting | < 10ms |
| llama3.2 first token (CPU) | ~2s |
| Full response (CPU) | ~10–15s |

GPU inference (NVIDIA 8GB+ VRAM) would reduce total response time to ~3–5s.

### 2.3 Failure Handling

| Failure | Detection | Response |
|---|---|---|
| Ollama unreachable | `ollama.AsyncClient` raises `ConnectError` | Caught in `event_stream()`, streams `{"type":"error","message":"Could not reach Ollama..."}` to frontend |
| bge-m3 unavailable at startup | `_verify_model()` probe fails | Falls back to `nomic-embed-text`; warns in logs; continues with fallback |
| BM25 package missing | Import error | KB runs semantic-only; `bm25=False` in health check |
| LLM timeout (no tokens) | Frontend `AbortSignal.timeout` | "Request timed out" with Retry button |
| Malformed SSE chunk | `try/except` in frontend `JSON.parse` | Silently skips malformed frame, stream continues |
| File upload failure | HTTP 413 / 415 / 422 | Shown as inline error in sidebar |
| Rate limit exceeded | slowapi `429` | "Too many requests" error in frontend |
| React component crash | `ErrorBoundary` | Recovery UI shown instead of blank page |

### 2.4 Conversation Context Design

Every call to `/api/chat` is **stateless at the HTTP level**. Context is reconstructed server-side from:

1. `conversationId` → last 12 DB messages
2. `userId` → stored profile attributes
3. `caseId` → onboarding stage + checklist state

This means any server restart or horizontal scale-out is safe — context is always in the database, never in memory.

---

## 3. Accuracy, Limitations, and Optional Features

### 3.1 Accuracy Considerations

**Retrieval accuracy:** Benchmarked at **22/24 test queries correct** using a hybrid BM25 + bge-m3 semantic + RRF fusion pipeline with policy-specific boosting. The two failing cases (`PTO policy`, `birth of child leave`) are vocabulary gaps between US/informal phrasing and the UK-style policy document — not retrieval logic errors.

**Answer grounding:** The LLM is constrained to answer exclusively from retrieved `<policy_context>`. Temperature 0.05 and an 8-rule system prompt prevent hallucination. Every response must cite the section used.

**Calculation accuracy:** When the user provides personal context (tenure, employment type), the LLM is instructed to apply policy tables to compute their specific entitlement. A memory extractor automatically stores discovered profile facts in SQLite so calculations are consistent across sessions.

**Confidence scoring:** Every response carries a blended confidence score (0.6× top retrieval score + 0.4× average of top 3). Displayed as a UX label:

| Score | Label | Meaning |
|---|---|---|
| ≥ 0.6 | High confidence (green) | Strong KB match |
| 0.3–0.6 | Moderate confidence (yellow) | Reasonable match, review sources |
| < 0.3 | Low confidence (amber) | Verify with HR |
| Deflection | Not found in policy (grey) | Out-of-scope query |

### 3.2 Known Limitations

| Limitation | Severity | Mitigation |
|---|---|---|
| **Stale KB** — if `knowledge_base.md` is outdated, answers reflect old policy | High | Live document watcher + upload API; warn on answer that policy should be current |
| **CPU-only inference** — 10–15s per response on a laptop without GPU | Medium | Streaming hides most of the wait; GPU deployment reduces to 3–5s |
| **No personal data access** — cannot check actual leave balances, payroll, manager | Medium | Clearly stated in footer: "Verify important decisions with HR directly" |
| **llama3.2 quality ceiling** — smaller model, occasional imprecise paraphrasing | Medium | System prompt enforces quoting; cite section so user can verify |
| **English only** — no multi-language support | Low | Scope defined as English HR policy |
| **Not legal advice** — policy answers are informational only | High | Footer disclaimer; out-of-scope escalation to HR |

### 3.3 Explainability UX

The system surfaces three explainability signals on every AI response:

**1. Source citations**
Every answer shows the exact KB section(s) used (e.g., *"1.10 Paternity Leave"*). The user can cross-check against the raw policy document.

**2. Confidence badge**
Colour-coded label tells the user how strongly the retrieval matched before they read the answer. Amber badge signals "check this with HR."

**3. Debug endpoint**
`GET /api/debug/retrieve?q=<query>` shows developers exactly which chunks were retrieved and their scores — separating retrieval failures from generation failures.

### 3.4 Feedback Controls

**Per-message feedback (👍 / 👎)**
- Every AI response has thumbs-up / thumbs-down buttons
- Stored in `feedback` table with `messageId`, `conversationId`, `value`, `timestamp`
- Accessible via `GET /api/audit/feedback`
- Currently used for observability (not yet fed back into retrieval weights — planned)

**Escalation**
- "Get Human Help" button creates a formal escalation record linked to the user's onboarding case
- Escalation captured with reason, timestamp, and status (`open → assigned → resolved`)
- HR can view open escalations via `GET /api/admin/stats`

**Admin feedback dashboard**
`GET /api/admin/evaluation` returns aggregate Recall@K, faithfulness, and relevance scores across all queries — enabling HR or engineering teams to monitor answer quality over time.

---

## 4. Backend Service Architecture — Orchestration of LLM Calls, Tools, and Logic

### 4.1 Service Map

```
                    ┌──────────────────────────────────────────────┐
                    │          FastAPI (main.py — port 8080)        │
                    │                                              │
  POST /api/chat ──►│  1. Validate (Pydantic)                      │
                    │  2. Rate check (slowapi)                      │
                    │  3. Load user profile + case context         │
                    │  4. Load conversation history (SQLite)        │
                    │         │                                    │
                    │         ▼                                    │
                    │  ┌─────────────────────────────────────┐     │
                    │  │        Query Rewriter               │     │
                    │  │  • regex abbreviation expansion     │     │
                    │  │  • synonym dictionary (50+ terms)   │     │
                    │  │  • difflib fuzzy correction         │     │
                    │  └──────────────┬──────────────────────┘     │
                    │                 │                            │
                    │         ┌───────┴───────┐                   │
                    │         ▼               ▼                   │
                    │    BM25 Search    bge-m3 Semantic            │
                    │    (top 20)       (top 20, async)            │
                    │         │               │                   │
                    │         └───────┬───────┘                   │
                    │                 ▼                            │
                    │           RRF Fusion                         │
                    │           Policy boosts (3×/2×)              │
                    │           Guaranteed section injection        │
                    │                 │                            │
                    │                 ▼                            │
                    │           Reranker (top 8)                   │
                    │                 │                            │
                    │                 ▼                            │
                    │  ┌──────────────────────────────────────┐    │
                    │  │           LLM Handler                │    │
                    │  │  • profile context prefix            │    │
                    │  │  • <policy_context> XML block        │    │
                    │  │  • 8-rule grounding system prompt    │    │
                    │  │  • ollama.AsyncClient.chat(stream=T) │    │
                    │  └──────────────┬───────────────────────┘    │
                    │                 │                            │
                    │         ◄───────┘  SSE token stream          │
                    │                                              │
                    │  Post-response (async, non-blocking):        │
                    │  • save_exchange() → SQLite                  │
                    │  • extract_profile_facts() → user profile    │
                    │  • generate_follow_up_questions()            │
                    │  • log_evaluation() → eval_log table         │
                    └──────────────────────────────────────────────┘
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
                     Ollama (11434)            SQLite (data/)
                     • llama3.2                • hr_copilot.db
                     • bge-m3                 • embeddings_cache.db
```

### 4.2 Orchestration Sequence (Single Request)

```
1.  Validate request body (Pydantic — field types, lengths, blank check)
2.  Apply rate limit (20 req/min per IP via slowapi)
3.  Load user profile from users table → build profile context string
4.  Load case context if caseId provided → inject stage + checklist
5.  Load last 12 turns from messages table → LLM history
6.  Query rewriter → expand synonyms + correct typos → extra_queries[]
7.  BM25 search on original + extra_queries → ranked list A (top 20)
8.  bge-m3 semantic search on original + extra_queries → ranked list B (top 20)
    (runs in thread pool via run_in_executor — does not block event loop)
9.  RRF fusion of A + B → single merged ranking
10. Apply policy title boost (3×) + content keyword boost (2×)
11. Guaranteed section injection (tenure table, WFH days table, sick leave policy)
12. Reranker selects final top 8 chunks
13. Build LLM messages array:
      [system prompt] + [history turns] + [profile prefix + user message + <policy_context>]
14. ollama.AsyncClient.chat(stream=True) → AsyncGenerator of tokens
15. Yield each token as SSE: data: {"type":"token","text":"..."}
16. On stream complete:
    a. save_exchange() → conversations + messages tables
    b. extract_profile_facts() on user message → update user profile if new facts found
    c. generate_follow_up_questions() from kb_results → 2-3 clickable suggestions
    d. log_evaluation() → recall@k, faithfulness, relevance scores
    e. Yield done event with sources, confidence, follow_ups, eval
```

### 4.3 Tool Integrations

| Tool | Purpose | Failure mode |
|---|---|---|
| **Ollama** (`llama3.2`) | Chat generation | Caught → streams error event to client |
| **Ollama** (`bge-m3`) | Dense retrieval embeddings | Falls back to `nomic-embed-text` |
| **rank-bm25** | Sparse keyword retrieval | Disabled gracefully; semantic-only mode |
| **SQLite** | Conversations, users, cases, eval | WAL journal mode prevents corruption |
| **watchdog** | Live KB file watcher | Falls back to 30-second polling |
| **slowapi** | Per-IP rate limiting | Returns HTTP 429 |
| **sentence-transformers** (optional) | CrossEncoder reranker | Falls back to Ollama-based scoring |

### 4.4 Background / Async Pattern

The FastAPI app uses a **lifespan context manager** for startup:
```python
@asynccontextmanager
async def lifespan(app):
    init_db()
    knowledge_base = KnowledgeBase(...)   # indexes all documents, builds BM25 + vectors
    llm_handler    = LLMHandler(...)
    query_rewriter = QueryRewriter(...)
    doc_watcher    = DocumentWatcher(knowledge_base)
    doc_watcher.start()                   # background thread watching knowledge_docs/
    yield
    doc_watcher.stop()
```

Blocking operations (embedding generation, BM25 search) run in a `ThreadPoolExecutor` via `loop.run_in_executor()` to avoid blocking the async event loop.

---

## 5. Responsible AI and Governance Note

### 5.1 Intended Use

This system is designed for **one specific purpose**: answering employee questions about Acme Corp's internal HR policies. It is not a general-purpose assistant, legal advisor, or HR case management system.

**Intended users:** Acme Corp employees seeking policy information (leave, remote work, benefits, grievances, onboarding guidance).

**Intended operating context:** Internal enterprise deployment, accessible only within company infrastructure.

### 5.2 What This System Will Not Do

The system prompt explicitly prohibits the LLM from:
- Using training knowledge about HR law, employment legislation, or generic HR practice
- Answering questions not covered by the retrieved policy document
- Inferring, guessing, or saying "typically" or "usually"
- Providing legal advice, disciplinary recommendations, or confidential HR case decisions

Out-of-scope queries receive a fixed deflection:
> *"I could not find that information in our HR policy. Please contact HR at hr@company.com."*

### 5.3 Accuracy Considerations

- **Ground truth is the KB.** If `knowledge_base.md` is outdated, answers will reflect the old policy. The KB must be kept current by HR. The document watcher supports live updates without restarts.
- **The confidence badge is a retrieval signal**, not a model probability. A high-confidence answer means the retrieval strongly matched — it does not guarantee the LLM interpreted it correctly.
- **Calculations are grounded** but should be verified for consequential decisions (pay, legal entitlements). The footer displays: *"Verify important decisions with HR directly."*
- **Temperature 0.05** minimises creative generation but does not eliminate it entirely. The LLM may occasionally paraphrase rather than quote verbatim.

### 5.4 Data Handling

- **No data leaves the machine.** All inference (llama3.2, bge-m3) runs locally via Ollama. No API calls to OpenAI, Anthropic, or any third party.
- **Conversation data** is stored in a local SQLite database (`data/hr_copilot.db`). It is not shared or transmitted.
- **User identity** is a random UUID + generated username (e.g., `swift-falcon-4291`). No PII is required or stored.
- **Profile data** (tenure, role, department) is stored only if the user volunteers it in conversation or via the profile API.

### 5.5 User Feedback Handling

| Signal | Collection | Current use | Planned use |
|---|---|---|---|
| 👍 Helpful | Per-message button | Stored in `feedback` table | Boost retrieval weights for matched sections |
| 👎 Not helpful | Per-message button | Stored in `feedback` table | Investigate low-confidence answers, update KB |
| HR escalation | "Get Human Help" button | Creates escalation record; HR notified | Feed into KB gaps analysis |
| Eval metrics | Automatic per query | Admin dashboard | Trigger KB review when Recall@K drops |

Feedback data is accessible to HR administrators via the admin API (`GET /api/admin/evaluation`, `GET /api/audit/feedback`) under bearer token authentication.

### 5.6 Human Oversight

- Every AI answer **cites the source section** — users can verify against the original policy document.
- The **confidence badge** flags low-confidence answers for human review.
- The **HR escalation path** is always one click away for any query the user is uncertain about.
- **Admin observability** (Recall@K, faithfulness, confidence distribution) allows HR or engineering to monitor for quality degradation over time.
- HR can **update the KB at any time** (edit `knowledge_base.md` or drop files in `knowledge_docs/`) and changes take effect within 30 seconds without restarting the system.

### 5.7 Bias and Fairness Considerations

- The system answers only from the policy document — it applies the **same policy rules to all users**, regardless of background or identity.
- Personal profile data (tenure, department, role) is used only to **calculate entitlements** from policy tables (e.g., tenure-based leave tiers). It is not used for differential treatment.
- If the underlying HR policy itself contains bias, the system will reflect it — this is a governance responsibility for HR, not the AI system.

---

## Appendix — File Responsibility Map

| File | Responsibility |
|---|---|
| `backend/main.py` | API routing, orchestration, rate limiting, CORS |
| `backend/knowledge_loader.py` | Hybrid RAG: BM25 + semantic + RRF + boosting + guaranteed injection |
| `backend/bm25_index.py` | Sparse keyword index (rank-bm25) |
| `backend/embeddings.py` | Dense embeddings (bge-m3 via Ollama) + SQLite cache |
| `backend/query_rewriter.py` | Synonym expansion, typo correction |
| `backend/reranker.py` | CrossEncoder / Ollama cross-encoder reranking |
| `backend/llm_handler.py` | Ollama chat streaming, grounding prompt, profile injection |
| `backend/followup_generator.py` | Rule-based follow-up question suggestions |
| `backend/profile_extractor.py` | Regex memory extraction from conversation text |
| `backend/database.py` | SQLite schema, migrations, all DB queries |
| `backend/user_manager.py` | User identity, profile, session management |
| `backend/case_manager.py` | Onboarding workflow cases, stages, escalations |
| `backend/evaluation.py` | Recall@K, faithfulness, relevance scoring |
| `backend/document_loader.py` | PDF/DOCX/CSV/MD parser |
| `backend/document_watcher.py` | Live file watcher for `knowledge_docs/` |
| `frontend/src/App.tsx` | Chat state, SSE stream reader, profile extraction trigger |
| `frontend/src/components/ChatMessage.tsx` | Message rendering, confidence badge, follow-up chips |
| `frontend/vite.config.ts` | Proxy: `/api` → `127.0.0.1:8080` (IPv4 explicit) |
