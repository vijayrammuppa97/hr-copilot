# Git Commit Guide — HR Knowledge Copilot

This document records the intended commit history for the HR Knowledge Copilot project.
Each commit represents a coherent, reviewable unit of work. Use `init_git_history.sh`
to replay this history from scratch.

---

## Commit Message Convention

All commits follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
<type>(<scope>): <short summary>

<body — what and why, wrapped at 72 chars>
```

| Type | When to use |
|------|------------|
| `chore` | Build setup, config, tooling, dependencies |
| `feat` | New application functionality |
| `docs` | Documentation only |
| `fix` | Bug fix |
| `refactor` | Code restructure with no behaviour change |
| `release` | Version tag commits |

Scope is optional but recommended: `frontend`, `backend`, `types`, `data`.

---

## Commit History (chronological)

---

### Commit 1 — Project Scaffold

```
chore: initialise project scaffold with Vite and FastAPI

Set up monorepo structure with React/TypeScript frontend (Vite, Tailwind
CSS) and Python FastAPI backend. Configures TypeScript strict mode,
PostCSS pipeline, and environment variable templates for development
and production deployment.
```

**Files staged:**
```
.gitignore
.env.example
backend/.env.example
backend/requirements.txt
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/postcss.config.js
frontend/tailwind.config.js
frontend/tsconfig.json
frontend/tsconfig.node.json
frontend/vite.config.ts
```

**Why this grouping:** Config and tooling files have no runtime behaviour — they
define the project's build contract and belong in a single scaffolding commit
before any source code is added.

---

### Commit 2 — Knowledge Base

```
docs(data): add HR policy knowledge base with 5 policy categories

Creates the static markdown knowledge base used as the sole authoritative
source for all AI responses. Covers leave entitlements, remote work
guidelines, onboarding processes, employee benefits, and escalation
procedures across 58 searchable sections.
```

**Files staged:**
```
data/knowledge_base.md
```

**Why this grouping:** The knowledge base is a domain artefact (HR content),
not application code. Keeping it in its own commit makes policy changes easy
to review in isolation via `git log -- data/knowledge_base.md`.

---

### Commit 3 — React App Entry Point

```
feat(frontend): scaffold React 18 app entry point with Tailwind styles

Bootstraps the Vite entry point, global CSS reset with Tailwind base
layers, and Vite environment type declarations. Establishes the root DOM
mounting point and base typography tokens.
```

**Files staged:**
```
frontend/src/index.tsx
frontend/src/index.css
frontend/src/vite-env.d.ts
```

**Why this grouping:** These three files are the minimal viable frontend —
nothing else in `src/` compiles without them. The `vite-env.d.ts` declaration
file is needed immediately because `import.meta.env` is referenced in `App.tsx`.

---

### Commit 4 — TypeScript Types

```
feat(types): define shared TypeScript interfaces for messages and feedback

Introduces Message, ChatRequest, ChatResponse, FeedbackValue, and
FeedbackRequest interfaces used across all frontend components. Centralises
the data contract so components never duplicate or drift from the
backend API shape.
```

**Files staged:**
```
frontend/src/types/index.ts
```

**Why this grouping:** Type definitions are the contract between components.
Committing them before the components that depend on them mirrors the
correct dependency order and makes the type design reviewable on its own.

---

### Commit 5 — Chat UI Components

```
feat(frontend): build ChatInput and ChatMessage UI components

Implements the auto-resizing message input bar (Shift+Enter for newline,
Enter to submit) and the message bubble renderer. ChatMessage includes a
confidence bar, KB source chips, thumbs up/down feedback buttons with
optimistic confirmation text, and an inline retry button for error messages.
```

**Files staged:**
```
frontend/src/components/ChatInput.tsx
frontend/src/components/ChatMessage.tsx
```

**Why this grouping:** These two components are pure presentational units —
they render props and emit callbacks, owning no state. Grouping them together
makes it clear they are the view layer, separate from the state machine in App.

---

### Commit 6 — App State and Conversation Orchestration

```
feat(frontend): implement App state machine with conversation orchestration

Wires together message sending, optimistic UI updates, retry on failure,
feedback submission, 32-second AbortSignal timeout guard (matching the
backend's 30s limit), and localStorage persistence for messages and
conversationId across page reloads and server restarts.
```

**Files staged:**
```
frontend/src/App.tsx
```

**Why this grouping:** App.tsx is the controller — it owns all mutable state
(`messages`, `isLoading`, `error`, `lastFailedMessage`) and all side effects.
A dedicated commit makes it easy to audit the state machine independently of
the presentational components.

---

### Commit 7 — FastAPI Backend Server

```
feat(backend): bootstrap FastAPI server with rate limiting, CORS, and chat API

Configures FastAPI with slowapi rate limiting (10 req/min per IP on
/api/chat, 30/min on /api/feedback), CORS middleware restricted to
configured origins, Pydantic v2 request/response validation, in-process
conversation store capped at 12 messages per session, 30-second asyncio
timeout on LLM calls, and a /health liveness endpoint.
```

**Files staged:**
```
backend/main.py
```

**Why this grouping:** `main.py` is the HTTP boundary — it handles routing,
validation, rate limiting, and conversation state. The LLM and KB are
injected as singletons, so this commit shows the server skeleton independently
of AI or search logic.

---

### Commit 8 — Claude API Integration

```
feat(backend): integrate Anthropic SDK with grounded generation and caching

Implements LLMHandler using AsyncAnthropic with prompt caching
(cache_control: ephemeral) to reduce per-request latency on repeated
system prompt prefixes. Constructs the grounded system prompt, injects
retrieved KB sections as a structured <policy_context> XML block, and
estimates response confidence from KB hit count (0.60–0.92 range).
```

**Files staged:**
```
backend/llm_handler.py
```

**Why this grouping:** The LLM integration is the AI core of the application.
Isolating it in one commit makes it straightforward to swap the model provider
or adjust the system prompt without touching routing or retrieval logic.

---

### Commit 9 — Knowledge Base Retrieval and Search

```
feat(backend): implement Jaccard similarity search over markdown knowledge base

Parses knowledge_base.md into sections on ## / ### headings, tokenises
content (lowercased, stop words removed), and ranks sections by Jaccard
overlap with a 1.5x heading-match boost. Returns top-5 matching sections
as structured dicts injected into the LLM context window.
```

**Files staged:**
```
backend/knowledge_loader.py
```

**Why this grouping:** The retrieval layer is independently testable and
replaceable (e.g., upgrade to BM25 or dense embeddings later) without
touching the HTTP layer or LLM handler. A standalone commit preserves that
seam clearly in history.

---

### Commit 10 — Error Handling and Accessible Loading State

```
feat(frontend): add ErrorBoundary and LoadingSkeleton for resilient UX

Wraps the app in a React class-based ErrorBoundary that catches unhandled
render exceptions and offers Try again / Reload page recovery controls.
Adds an accessible LoadingSkeleton (role=status, aria-label, aria-busy)
with a pulsing 4-line + 2-chip placeholder that replaces a plain spinner
while awaiting AI responses.
```

**Files staged:**
```
frontend/src/components/ErrorBoundary.tsx
frontend/src/components/LoadingSkeleton.tsx
```

**Why this grouping:** Error handling and loading states are cross-cutting
resilience concerns. They are not core chat features and can be reviewed,
tested, and modified independently of ChatMessage or App logic.

---

### Commit 11 — Responsible AI Documentation

```
docs: add responsible AI documentation covering safety and governance

Documents intended use and prohibited uses, known system limitations
(static KB, no personalisation, hallucination risk), accuracy approach
(RAG confidence scoring, validation test suite), user feedback handling
process, HR escalation paths, production monitoring metrics and alert
thresholds, bias mitigation strategies, and data privacy controls.
```

**Files staged:**
```
RESPONSIBLE_AI.md
```

**Why this grouping:** Responsible AI documentation is a governance deliverable
that should be independently reviewable by HR, Legal, and Compliance without
having to parse source code. A separate commit keeps it visible in `git log`.

---

### Commit 12 — Architecture and Developer Documentation

```
docs: add architecture, prompt design, and developer README

ARCHITECTURE.md: full ASCII system diagram, step-by-step data flow for chat
and feedback, React component tree, backend module responsibility table,
scalability path from single-process to Kubernetes, and guidance on handling
larger knowledge bases with dense embeddings.

PROMPT_DESIGN.md: system prompt with per-rule rationale, RAG retrieval
algorithm design, conversation history windowing strategy, Claude model
selection reasoning, and seven prompt engineering techniques used.

README.md: quick-start guide, environment variable reference, two-terminal
run instructions, and production deployment notes.
```

**Files staged:**
```
README.md
ARCHITECTURE.md
PROMPT_DESIGN.md
```

**Why this grouping:** These three documents form the developer-facing
knowledge base for the project. Grouping them in one commit signals that they
are a documentation suite, not scattered notes.

---

### Commit 13 — Release v1.0.0

```
release: v1.0.0 — complete HR Knowledge Copilot

Application is feature-complete: RAG-powered chat with Jaccard KB
retrieval, thumbs up/down feedback with optimistic UI, retry on error,
accessible loading skeleton, per-IP rate limiting, 30-second server
timeout, CORS, Anthropic prompt caching, in-process conversation history,
and a full responsible-AI and developer documentation suite.

Tagged v1.0.0.
```

**Files staged:**
```
COMMIT_GUIDE.md
init_git_history.sh
```

**Tag created:** `v1.0.0`

**Why this grouping:** The commit guide and init script are meta-artefacts
about the repository itself. Placing them in the final commit means they are
present in the `v1.0.0` snapshot and can be reviewed alongside the full
application.

---

## Quick Reference Table

| # | Commit subject | Type | Key files |
|---|---------------|------|-----------|
| 1 | Initialise project scaffold | `chore` | `package.json`, `requirements.txt`, config files |
| 2 | Add HR policy knowledge base | `docs(data)` | `knowledge_base.md` |
| 3 | Scaffold React 18 entry point | `feat(frontend)` | `index.tsx`, `index.css`, `vite-env.d.ts` |
| 4 | Define TypeScript interfaces | `feat(types)` | `types/index.ts` |
| 5 | Build ChatInput and ChatMessage | `feat(frontend)` | `ChatInput.tsx`, `ChatMessage.tsx` |
| 6 | Implement App state machine | `feat(frontend)` | `App.tsx` |
| 7 | Bootstrap FastAPI server | `feat(backend)` | `main.py` |
| 8 | Integrate Claude API | `feat(backend)` | `llm_handler.py` |
| 9 | Add KB retrieval and search | `feat(backend)` | `knowledge_loader.py` |
| 10 | Add ErrorBoundary and skeleton | `feat(frontend)` | `ErrorBoundary.tsx`, `LoadingSkeleton.tsx` |
| 11 | Responsible AI documentation | `docs` | `RESPONSIBLE_AI.md` |
| 12 | Architecture and README docs | `docs` | `README.md`, `ARCHITECTURE.md`, `PROMPT_DESIGN.md` |
| 13 | Release v1.0.0 | `release` | `COMMIT_GUIDE.md`, `init_git_history.sh` |

---

## Running the Init Script

```bash
# Navigate into the project root
cd hr-copilot-final

# Make the script executable (macOS / Linux / Git Bash on Windows)
chmod +x init_git_history.sh

# Run with default author (HR Copilot Bot <hr-tech@acme.com>)
bash init_git_history.sh

# Run with your own identity
GIT_AUTHOR_NAME="Your Name" GIT_AUTHOR_EMAIL="you@example.com" bash init_git_history.sh
```

After the script completes, verify the history:

```bash
git log --oneline
# Expected: 13 commits + v1.0.0 tag

git tag
# Expected: v1.0.0

git show v1.0.0 --stat
# Expected: shows the release commit with COMMIT_GUIDE.md and init_git_history.sh
```

---

## Amending a Commit Message

If you need to fix a commit message before pushing:

```bash
# Fix the most recent commit
git commit --amend -m "corrected message"

# Fix an older commit (interactive rebase — last 3 commits)
git rebase -i HEAD~3
# Change 'pick' to 'reword' on the line you want to fix, save, then edit the message
```

---

*This guide is part of the v1.0.0 release. Update it when adding future commits.*
