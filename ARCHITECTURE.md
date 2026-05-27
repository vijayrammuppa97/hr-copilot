# Architecture — HR Knowledge Copilot

**Document owner:** HR Technology / Engineering  
**Version:** 1.0 | **Last reviewed:** January 2025 | **Next review:** July 2025  
**Audience:** Engineering leads, DevOps, system operators

---

## 1. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    React 18 + TypeScript (Vite)                  │   │
│  │                                                                  │   │
│  │   ┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐  │   │
│  │   │   App.tsx   │   │  ChatMessage.tsx  │   │ LoadingSkeleton  │  │   │
│  │   │  (state +   │──▶│  (message bubble  │   │    .tsx         │  │   │
│  │   │   logic)    │   │  + feedback UI)   │   │  (skeleton UI)  │  │   │
│  │   └──────┬──────┘   └──────────────────┘   └─────────────────┘  │   │
│  │          │                                                        │   │
│  │   ┌──────▼──────┐   ┌──────────────────┐   ┌─────────────────┐  │   │
│  │   │  ChatInput  │   │  ConfidenceBar   │   │  ErrorBoundary  │  │   │
│  │   │   .tsx      │   │    .tsx          │   │     .tsx        │  │   │
│  │   └─────────────┘   └──────────────────┘   └─────────────────┘  │   │
│  │                                                                  │   │
│  │   localStorage: conversationId, messages[]                       │   │
│  └──────────────────────────┬───────────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │  HTTP (fetch)
                              │  POST /api/chat
                              │  POST /api/feedback
                              │  GET  /health
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BACKEND SERVER                                  │
│                         FastAPI + Uvicorn                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         main.py                                  │   │
│  │                                                                  │   │
│  │   Middleware: CORS, Rate Limiter (slowapi, 10 req/min per IP)   │   │
│  │                                                                  │   │
│  │   POST /api/chat ─────────────────────────────────────┐         │   │
│  │     1. Validate ChatRequest (Pydantic)                │         │   │
│  │     2. Load conversation history (in-memory dict)     │         │   │
│  │     3. Search knowledge base ─────────────────────────┼──▶ KB  │   │
│  │     4. Call LLM with timeout (30s) ───────────────────┼──▶ LLM │   │
│  │     5. Update conversation store                      │         │   │
│  │     6. Return ChatResponse                            │         │   │
│  │                                                       │         │   │
│  │   POST /api/feedback ─────────────────────────────────┘         │   │
│  │     1. Validate FeedbackRequest                                  │   │
│  │     2. Log signal (console/file)                                 │   │
│  │     3. Return {"status": "recorded"}                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐   │
│  │  knowledge_loader.py │    │          llm_handler.py              │   │
│  │                      │    │                                      │   │
│  │  KnowledgeBase       │    │  LLMHandler                         │   │
│  │  - Parse markdown    │    │  - AsyncAnthropic client            │   │
│  │  - Jaccard search    │    │  - Prompt caching (ephemeral)       │   │
│  │  - Heading boost     │    │  - KB context injection             │   │
│  │  - Top-5 results     │    │  - Confidence estimation            │   │
│  └──────────────────────┘    └─────────────────┬────────────────────┘   │
│                                                │                        │
│  ┌──────────────────────┐                      │                        │
│  │  data/knowledge_     │                      │                        │
│  │  base.md             │                      │                        │
│  │  (static file,       │                      │                        │
│  │   ~58 sections)      │                      │                        │
│  └──────────────────────┘                      │                        │
└────────────────────────────────────────────────┼────────────────────────┘
                                                 │  HTTPS
                                                 │  Anthropic Messages API
                                                 ▼
                                    ┌────────────────────────┐
                                    │    Anthropic API       │
                                    │  claude-sonnet-4-6     │
                                    │  (external service)    │
                                    └────────────────────────┘
```

### Port assignments (development)

| Service | Default port | Configured via |
|---------|-------------|----------------|
| Frontend (Vite dev server) | 5173 | `vite.config.ts` |
| Backend (Uvicorn) | 8000 | `uvicorn main:app --port 8000` |
| Anthropic API | 443 (HTTPS) | SDK default |

---

## 2. Data Flow Explanation

### 2.1 Chat request flow (happy path)

```
User types question → ChatInput submits → App.tsx sendMessage()
    │
    ▼
POST /api/chat  { message, conversationId }
    │
    ├─▶ Rate limit check (slowapi: 10/min per IP)
    │       └─ 429 Too Many Requests if exceeded
    │
    ├─▶ Pydantic validation (message 1–2000 chars, conversationId 1–100 chars)
    │       └─ 422 Unprocessable Entity if invalid
    │
    ├─▶ Load conversation history from _conversation_store[cid]
    │       └─ Empty list if first message in session
    │
    ├─▶ KnowledgeBase.search(message, top_k=5)
    │       ├─ Tokenise query (lowercase, remove stop words)
    │       ├─ Jaccard similarity against each KB section
    │       ├─ Apply 1.5× heading boost
    │       └─ Return top-5 {section, content} dicts
    │
    ├─▶ asyncio.wait_for(LLMHandler.generate(...), timeout=30s)
    │       ├─ Build system prompt with <policy_context> injected
    │       ├─ Send to Anthropic Messages API (cached system prompt)
    │       ├─ Receive response_text
    │       └─ Estimate confidence from KB hit count
    │           └─ 504 Gateway Timeout if > 30s
    │
    ├─▶ Append exchange to _conversation_store[cid], trim to 12 entries
    │
    └─▶ Return ChatResponse { message, sources, confidence, timestamp }
            │
            ▼
        App.tsx receives response → appends assistant Message to state
            │
            ├─▶ ChatMessage renders bubble with confidence bar + sources
            └─▶ localStorage updated with full message list
```

### 2.2 Feedback flow

```
User clicks 👍 or 👎 on a ChatMessage
    │
    ▼
App.tsx handleFeedback(messageId, value)
    │
    ├─▶ Optimistic update: setMessages() → marks message.feedback = value
    │       └─ UI updates instantly (thumbs highlight, confirmation text shown)
    │
    └─▶ POST /api/feedback { messageId, conversationId, feedback }  (best-effort)
            ├─ 200 OK → {"status": "recorded"}
            └─ Error → silently ignored (non-critical path)
```

### 2.3 Client-side persistence

On every state update, `App.tsx` writes to `localStorage`:
- `hr_copilot_messages` — full array of `Message` objects (JSON)
- `hr_copilot_conversation_id` — opaque UUID string

On mount, the app reads these keys and rehydrates state, giving the appearance of persistent history even across page reloads and server restarts.

---

## 3. Component Interactions

### 3.1 Frontend component tree

```
<ErrorBoundary>                    ← catches unhandled render errors
  <App>                            ← owns all state; orchestrates data flow
    <div.chat-container>
      <header>                     ← static branding + status indicator
      <div.messages-area>
        <ChatMessage>              ← renders each message bubble
          <ConfidenceBar>          ← visual confidence indicator (assistant only)
          <SourcesList>            ← KB section tags (assistant only)
          <FeedbackButtons>        ← 👍/👎 (assistant only, non-error)
          <RetryButton>            ← "Try again" (error messages only)
        </ChatMessage>
        ...
        <LoadingSkeleton>          ← shown while awaiting API response
      </div.messages-area>
      <ErrorBanner>                ← shown when sendMessage fails
      <ChatInput>                  ← textarea + send button
      <footer>                     ← AI disclaimer text
    </div.chat-container>
  </App>
</ErrorBoundary>
```

### 3.2 State managed in App.tsx

| State variable | Type | Purpose |
|---------------|------|---------|
| `messages` | `Message[]` | Full conversation history rendered in UI |
| `isLoading` | `boolean` | Controls LoadingSkeleton and input disabled state |
| `error` | `string \| null` | Error banner content |
| `lastFailedMessage` | `string \| null` | Stored for retry on failure |
| `conversationId` | `React.MutableRefObject<string>` | Stable UUID for the session (ref, not state — does not trigger re-render) |

### 3.3 Backend module responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | HTTP routing, rate limiting, request/response validation, conversation store, timeout enforcement, CORS, logging |
| `knowledge_loader.py` | Markdown parsing, tokenisation, Jaccard similarity search, result ranking |
| `llm_handler.py` | Anthropic SDK client, system prompt construction, prompt caching, confidence estimation |

### 3.4 Key interface: `/api/chat`

**Request:**
```json
{
  "message": "How many days of annual leave do I get?",
  "conversationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Response:**
```json
{
  "message": "After your first 2 years at Acme Corp, you receive 18 days of annual leave per year...\n\nFor personalised guidance, contact HR at hr@acme.com or speak with your HR Business Partner.",
  "sources": ["1.1 Annual Leave Entitlement", "1.2 Leave Accrual Schedule", "1.3 Carrying Over Leave"],
  "confidence": 0.92,
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

---

## 4. Scalability Considerations

### 4.1 Current architecture limits

The current implementation is a **single-process, in-memory** system suitable for low-to-moderate internal usage (estimated: up to ~50 concurrent users, ~5,000 requests/day).

| Component | Current limit | Bottleneck |
|-----------|--------------|------------|
| Conversation store | In-process dict | Lost on restart; single process only |
| Rate limiter | In-process (slowapi) | Resets on restart; not shared across processes |
| Knowledge base | Loaded once at startup | Requires restart to update |
| LLM throughput | 10 req/min per IP, 30s timeout | Anthropic API rate limits |
| Uvicorn | Single worker by default | Does not scale across CPU cores |

### 4.2 Horizontal scaling blockers

Running multiple backend instances creates two immediate problems:

1. **Conversation history is not shared** — a user hitting instance B after instance A has no prior context
2. **Rate limiting is not shared** — 10 req/min per IP is enforced per-process, not globally

Both require moving state out of process memory.

### 4.3 Scaling path (recommended progression)

**Stage 1: Multi-worker (2–4× capacity, same host)**
```
uvicorn main:app --workers 4
```
Requires: Move conversation store and rate limiter to Redis.

**Stage 2: Containerised deployment (10–20× capacity)**
- Docker container per service (frontend: Nginx, backend: Uvicorn + Gunicorn)
- Redis cluster for shared state
- Load balancer (e.g., AWS ALB or Nginx upstream) distributes requests
- Container orchestration (Docker Compose → Kubernetes)

**Stage 3: Production-grade (100×+ capacity)**
- Async task queue (Celery or ARQ) for LLM calls if streaming is not used
- Read replica for feedback database
- CDN for frontend static assets
- Horizontal pod autoscaling in Kubernetes based on CPU/request rate

---

## 5. Handling More Users and a Larger Knowledge Base

### 5.1 More concurrent users

| Problem | Solution |
|---------|----------|
| Conversation store grows unboundedly | Set per-conversation TTL in Redis (e.g., 24h idle expiry) |
| Rate limiter per-process | Replace slowapi in-memory store with Redis backend |
| Single backend process | Run behind a process manager (Gunicorn) with multiple Uvicorn workers |
| No observability at scale | Add Prometheus metrics endpoint; scrape with Grafana |

### 5.2 Larger knowledge base

The current Jaccard keyword search has O(n) complexity where n = number of KB sections. For a small KB (~58 sections), this is negligible. As the KB grows:

| KB size | Recommended retrieval approach |
|---------|-------------------------------|
| < 200 sections | Current Jaccard search (adequate) |
| 200–2,000 sections | Upgrade to BM25 (better term-frequency weighting, still lexical) |
| 2,000+ sections | Dense embeddings + vector store (semantic retrieval, handles paraphrase) |

**Embedding upgrade path:**
1. Generate embeddings for each KB section using `text-embedding-3-small` (OpenAI) or Anthropic's embedding endpoint
2. Store vectors in a vector database (Chroma, Pinecone, or pgvector on PostgreSQL)
3. Replace `knowledge_loader.py`'s `search()` with a vector similarity query
4. Cache embeddings — regenerate only when the KB file changes

**Knowledge base management at scale:**
- Move `knowledge_base.md` from a static file to a database table (one row per section)
- Build a simple admin UI for HR policy owners to add/edit/delete sections
- Trigger embedding regeneration on save (background job via task queue)
- Eliminate the "restart to reload KB" operational burden

### 5.3 Multi-tenancy (multiple departments or companies)

If the tool is extended to serve multiple HR knowledge bases (e.g., one per region or entity):
- Add a `tenantId` field to the chat request
- Route KB search and conversation history to tenant-scoped stores
- Apply per-tenant rate limits
- Maintain separate system prompts per tenant for policy-specific instructions

### 5.4 Observability at scale

At the current stage, logs are written to stdout. For production:

| Signal | Tool |
|--------|------|
| Structured logs | JSON format + centralized log aggregation (Datadog, CloudWatch, Loki) |
| Request metrics | Prometheus + Grafana (latency p50/p95/p99, error rate, confidence distribution) |
| LLM cost tracking | Anthropic usage API — track tokens per request, cache hit rate |
| Feedback analytics | Database table → weekly SQL report or BI tool (Metabase, Looker) |
| Uptime monitoring | External synthetic probe on `/health` endpoint |

---

*Questions about this document? Contact hr-tech@acme.com*  
*Changelog: v1.0 — January 2025 — Initial version*
