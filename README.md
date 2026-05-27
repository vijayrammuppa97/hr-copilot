# HR Knowledge Copilot

An AI-powered enterprise HR assistant that answers employee questions about company policies using Claude (Anthropic). Built with React + TypeScript on the frontend and FastAPI + Python on the backend.

---

## Project Overview

Employees ask natural-language HR questions ("How many sick days do I get?", "Can I work from abroad?") and receive accurate, sourced answers grounded in the company's HR policy document — no hallucinated policies, no generic advice.

**Key features:**
- Keyword-based retrieval from a curated HR knowledge base (Markdown)
- Claude AI generates empathetic, structured answers from retrieved context
- Confidence score and policy section citations shown on every response
- Conversation history (last 3 exchanges) for follow-up questions
- Chat history persisted to localStorage across page refreshes
- Rate limiting (10 requests/minute per IP)
- Graceful degradation when the AI service is unavailable

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     BROWSER (port 3000)                  │
│                                                          │
│   ┌──────────────┐   ┌─────────────────────────────┐    │
│   │  ChatInput   │   │       ChatMessage            │    │
│   │  (textarea)  │   │  bubble · sources · confidence│   │
│   └──────┬───────┘   └─────────────────────────────┘    │
│          │                        ▲                      │
│          ▼                        │                      │
│   ┌──────────────────────────────────────────────────┐   │
│   │                   App.tsx                        │   │
│   │  state: messages · loading · error · convoId     │   │
│   │  axios POST /api/chat  ◄──── localStorage        │   │
│   └──────────────────────┬───────────────────────────┘   │
└─────────────────────────┼───────────────────────────────┘
                           │  POST /api/chat
                           │  (Vite proxy → port 8000 in dev)
                           ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (port 8000)                │
│                                                          │
│  ┌────────────┐   ┌──────────────────────────────────┐  │
│  │  Rate      │   │           main.py                │  │
│  │  Limiter   │──►│  validate → search KB → call LLM │  │
│  │ 10 req/min │   └────────┬──────────────┬──────────┘  │
│  └────────────┘            │              │             │
│                            ▼              ▼             │
│              ┌─────────────────┐  ┌──────────────────┐  │
│              │ knowledge_      │  │  llm_handler.py  │  │
│              │ loader.py       │  │                  │  │
│              │                 │  │  system prompt   │  │
│              │ • Parse MD      │  │  (cached)        │  │
│              │ • Jaccard search│  │  + KB context    │  │
│              │ • Top-5 results │  │  + history[3]    │  │
│              └────────┬────────┘  └────────┬─────────┘  │
└───────────────────────┼────────────────────┼────────────┘
                        │                    │
                        ▼                    ▼
             ┌──────────────────┐  ┌─────────────────────┐
             │  data/           │  │   Anthropic API      │
             │  knowledge_      │  │   claude-sonnet-4-6  │
             │  base.md         │  │   max_tokens: 1024   │
             │  (58 sections)   │  └─────────────────────┘
             └──────────────────┘
```

**Data flow for a single chat request:**
1. User types a message → `ChatInput` calls `App.sendMessage()`
2. `App` adds the user message to state and POSTs to `/api/chat`
3. Backend validates the request (Pydantic) and checks the rate limit
4. `KnowledgeBase.search()` runs Jaccard similarity → top-5 matching sections
5. `LLMHandler.generate()` builds the prompt: system + KB context + last 3 turns
6. Claude returns a grounded answer; backend appends exchange to conversation store
7. Response `{message, sources, confidence, timestamp}` returned to frontend
8. `App` adds the assistant message to state → `ChatMessage` renders it
9. `useEffect` persists updated messages to `localStorage`

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repo-url>
cd hr-copilot-final
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
```

All other values have sensible defaults and can be left as-is for local development.

### 3. How to configure the API key

1. Go to **https://console.anthropic.com**
2. Sign in (or create a free account)
3. Navigate to **API Keys** in the left sidebar
4. Click **Create Key**, give it a name (e.g. `hr-copilot-dev`)
5. Copy the key — it starts with `sk-ant-`
6. Paste it into your `.env` file as `ANTHROPIC_API_KEY=sk-ant-...`
7. Add credits under **Plans & Billing** if the account balance is zero

> **Security:** Never commit `.env` to version control. It is already listed in `.gitignore`.

---

## Running the Application

### Backend

```bash
cd backend

# Create a virtual environment
python -m venv .venv

# Activate it
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

Verify the backend is running:
```bash
curl http://localhost:8000/health
# → {"status":"healthy","kb_sections":53,"model":"claude-sonnet-4-6","timestamp":"..."}
```

### Frontend

Open a **new terminal**:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

The app opens at **http://localhost:3000**

The Vite dev server automatically proxies `/api/*` requests to the backend on port 8000, so no CORS configuration is needed during development.

---

## Example User Questions

Copy any of these into the chat to test the system:

**Leave policy:**
- "How many annual leave days do I get?"
- "Can I carry over unused leave to next year?"
- "How do I apply for maternity leave?"
- "What counts as a valid reason for sick leave?"
- "How long is paternity leave?"

**Remote work:**
- "Can I work from home?"
- "How many days a week can I work remotely?"
- "What equipment does the company provide for remote work?"
- "Can I work from another country?"
- "What internet speed do I need to work from home?"

**Onboarding:**
- "What happens on my first day?"
- "What should I complete in my first week?"
- "How long is the probationary period?"
- "What is the buddy programme?"

**Benefits:**
- "What health insurance does the company offer?"
- "How does the 401k match work?"
- "Is there a gym allowance?"
- "What mental health support is available?"

**Escalation:**
- "How do I raise a grievance?"
- "Who is my HR Business Partner?"
- "How do I report harassment anonymously?"
- "What is the disciplinary process?"

---

## Project Structure

```
hr-copilot-final/
├── frontend/
│   ├── package.json          # React, TypeScript, Tailwind, Axios
│   ├── tsconfig.json         # Strict TypeScript config
│   ├── vite.config.ts        # Vite + /api proxy
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.tsx           # Chat state, API calls, localStorage
│       ├── index.tsx         # React entry point
│       ├── index.css         # Tailwind imports
│       ├── types/index.ts    # Shared TypeScript interfaces
│       └── components/
│           ├── ChatMessage.tsx   # Message bubble, sources, copy button
│           ├── ChatInput.tsx     # Textarea, char counter, submit
│           └── ErrorBoundary.tsx # Crash recovery UI
├── backend/
│   ├── main.py               # FastAPI app, CORS, rate limiting, routing
│   ├── knowledge_loader.py   # Markdown parser + Jaccard search
│   ├── llm_handler.py        # Anthropic SDK, prompt caching
│   └── requirements.txt
├── data/
│   └── knowledge_base.md     # HR policy document (58 sections)
├── .env                      # Your secrets (never commit)
├── .env.example              # Template — safe to commit
├── .gitignore
├── README.md
├── ARCHITECTURE.md           # Detailed system design
├── RESPONSIBLE_AI.md         # AI limitations and ethics
└── PROMPT_DESIGN.md          # Prompt engineering decisions
```

---

## API Reference

### `POST /api/chat`

**Request:**
```json
{
  "message": "How many sick days do I get?",
  "conversationId": "user-abc-123"
}
```

**Response:**
```json
{
  "message": "You receive 10 paid sick days per calendar year...",
  "sources": ["1.6 Sick Leave Policy", "1.7 Sick Leave Documentation"],
  "confidence": 0.92,
  "timestamp": "2025-05-27T10:30:00Z"
}
```

**Error responses:**
| Status | Meaning |
|--------|---------|
| `400` | Invalid request body (missing field, too long) |
| `429` | Rate limit exceeded (10 req/min per IP) |
| `503` | Claude API unavailable or not configured |

### `GET /health`

Returns server status, number of loaded KB sections, and active model.

---

## Known Limitations

### AI accuracy
- Answers are grounded in `data/knowledge_base.md`. If the file is outdated, answers will be too. **Update the file whenever HR policies change and restart the backend.**
- The confidence score is a heuristic (based on KB hit count), not a model probability. A high score does not guarantee a correct answer.
- Claude may occasionally paraphrase policy details rather than quoting them verbatim. Always direct employees to the official policy document for binding commitments.

### Scope
- The system only covers topics in `knowledge_base.md`. Questions outside this scope will receive an escalation response directing the employee to HR.
- The chatbot does not have access to personal employee data (leave balances, payroll, manager name). It answers policy questions only.
- Not suitable for legal advice, disciplinary decisions, or confidential HR case management.

### Infrastructure
- **Conversation history** is stored in memory (Python dict). It is lost if the server restarts. For production, replace with Redis.
- **Rate limiting** is in-process per IP. For multiple backend instances, replace with Redis-backed slowapi.
- **No authentication.** The `conversationId` is client-generated. In production, add JWT authentication so conversation history is properly scoped to authenticated users.
- The app is not designed for more than ~50 concurrent users without horizontal scaling.

### Model
- Requires an active Anthropic API key with a non-zero credit balance.
- Response quality depends on the Claude model version. The model is configurable via `CLAUDE_MODEL` in `.env`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `503 AI service unavailable` | No API credits | Add credits at console.anthropic.com |
| `429 Too Many Requests` | Rate limit hit | Wait 60 seconds and try again |
| Frontend shows "Failed to fetch" | Backend not running | Start uvicorn on port 8000 |
| `pydantic-core` build fails | Python version too new for pinned pydantic | Use `pydantic>=2.10.0` (unpinned) |
| `npm: command not found` | Node not in PATH | Restart terminal after installing Node.js |
| KB sections show 0 | Wrong `KB_PATH` in `.env` | Verify path is relative to `backend/` |

---

## License

Internal use only. Not for public distribution.
