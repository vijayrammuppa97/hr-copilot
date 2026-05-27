#!/usr/bin/env bash
# =============================================================================
# init_git_history.sh — Initialise the HR Knowledge Copilot git history
#
# Creates 13 commits that mirror the logical build order of the project,
# then tags the result as v1.0.0.
#
# Usage (run from the hr-copilot-final directory):
#   bash init_git_history.sh
#
# Override commit author:
#   GIT_AUTHOR_NAME="Your Name" GIT_AUTHOR_EMAIL="you@example.com" bash init_git_history.sh
# =============================================================================

set -euo pipefail

# ─── Colour helpers ───────────────────────────────────────────────────────── #

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${GREEN}→${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }
heading() { echo -e "\n${BOLD}$*${RESET}"; }

# ─── Directory guard ──────────────────────────────────────────────────────── #

REQUIRED_FILES=(
  "data/knowledge_base.md"
  "backend/main.py"
  "backend/llm_handler.py"
  "backend/knowledge_loader.py"
  "backend/requirements.txt"
  "frontend/src/App.tsx"
  "frontend/src/types/index.ts"
  "frontend/src/components/ChatInput.tsx"
  "frontend/src/components/ChatMessage.tsx"
  "frontend/src/components/ErrorBoundary.tsx"
  "frontend/src/components/LoadingSkeleton.tsx"
  "RESPONSIBLE_AI.md"
  "README.md"
  "ARCHITECTURE.md"
  "PROMPT_DESIGN.md"
  "COMMIT_GUIDE.md"
)

heading "HR Knowledge Copilot — Git History Initialiser"
echo ""

for f in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    error "Expected file not found: $f\nRun this script from the hr-copilot-final directory."
  fi
done
info "All required files present."

# ─── Existing history guard ───────────────────────────────────────────────── #

if [[ -d ".git" ]]; then
  COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
  if [[ "$COMMIT_COUNT" -gt 0 ]]; then
    warn "This repository already has $COMMIT_COUNT commit(s)."
    echo -e "   Running again will ${RED}fail on duplicate file adds${RESET}."
    echo ""
    read -r -p "   Reset and reinitialise? This deletes the existing git history. [y/N] " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
      rm -rf .git
      info "Existing .git directory removed."
    else
      echo "Aborted. No changes made."
      exit 0
    fi
  fi
fi

# ─── Git initialisation ───────────────────────────────────────────────────── #

if [[ ! -d ".git" ]]; then
  git init -b main > /dev/null 2>&1 || { git init > /dev/null 2>&1; git checkout -b main > /dev/null 2>&1 || true; }
  info "Initialised empty git repository on branch 'main'."
fi

# ─── Author identity ──────────────────────────────────────────────────────── #

GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-HR Copilot Bot}"
GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-hr-tech@acme.com}"
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

echo ""
echo -e "  Author : ${BOLD}$GIT_AUTHOR_NAME${RESET} <$GIT_AUTHOR_EMAIL>"
echo -e "  Override: GIT_AUTHOR_NAME='...' GIT_AUTHOR_EMAIL='...' bash $0"
echo ""

# ─── Commit helper ────────────────────────────────────────────────────────── #

COMMIT_NUM=0

commit() {
  local subject="$1"
  local body="$2"
  COMMIT_NUM=$(( COMMIT_NUM + 1 ))
  git commit -m "$(printf '%s\n\n%s' "$subject" "$body")" --quiet
  echo -e "  ${GREEN}✓${RESET} [${COMMIT_NUM}/13] $subject"
}

# ═════════════════════════════════════════════════════════════════════════════
heading "Replaying 13-commit history..."
echo ""
# ═════════════════════════════════════════════════════════════════════════════


# ─── Commit 1 — Project scaffold ──────────────────────────────────────────── #

git add \
  .gitignore \
  .env.example \
  backend/requirements.txt \
  frontend/index.html \
  frontend/package.json \
  frontend/postcss.config.js \
  frontend/tailwind.config.js \
  frontend/tsconfig.json \
  frontend/tsconfig.node.json \
  frontend/vite.config.ts

# package-lock.json is optional (present after npm install)
if [[ -f "frontend/package-lock.json" ]]; then
  git add frontend/package-lock.json
fi

# backend .env.example is optional (may be at root only)
if [[ -f "backend/.env.example" ]]; then
  git add backend/.env.example
fi

commit \
  "chore: initialise project scaffold with Vite and FastAPI" \
  "Set up monorepo structure with React/TypeScript frontend (Vite, Tailwind
CSS) and Python FastAPI backend. Configures TypeScript strict mode,
PostCSS pipeline, and environment variable templates for development
and production deployment."


# ─── Commit 2 — Knowledge base ────────────────────────────────────────────── #

git add data/knowledge_base.md

commit \
  "docs(data): add HR policy knowledge base with 5 policy categories" \
  "Creates the static markdown knowledge base used as the sole authoritative
source for all AI responses. Covers leave entitlements, remote work
guidelines, onboarding processes, employee benefits, and escalation
procedures across 58 searchable sections."


# ─── Commit 3 — React entry point ─────────────────────────────────────────── #

git add \
  frontend/src/index.tsx \
  frontend/src/index.css \
  frontend/src/vite-env.d.ts

commit \
  "feat(frontend): scaffold React 18 app entry point with Tailwind styles" \
  "Bootstraps the Vite entry point, global CSS reset with Tailwind base
layers, and Vite environment type declarations. Establishes the root DOM
mounting point and base typography tokens."


# ─── Commit 4 — TypeScript types ──────────────────────────────────────────── #

git add frontend/src/types/index.ts

commit \
  "feat(types): define shared TypeScript interfaces for messages and feedback" \
  "Introduces Message, ChatRequest, ChatResponse, FeedbackValue, and
FeedbackRequest interfaces used across all frontend components. Centralises
the data contract so components never duplicate or drift from the
backend API shape."


# ─── Commit 5 — Chat UI components ────────────────────────────────────────── #

git add \
  frontend/src/components/ChatInput.tsx \
  frontend/src/components/ChatMessage.tsx

commit \
  "feat(frontend): build ChatInput and ChatMessage UI components" \
  "Implements the auto-resizing message input bar (Shift+Enter for newline,
Enter to submit) and the message bubble renderer. ChatMessage includes a
confidence bar, KB source chips, thumbs up/down feedback buttons with
optimistic confirmation text, and an inline retry button for error messages."


# ─── Commit 6 — App state machine ─────────────────────────────────────────── #

git add frontend/src/App.tsx

commit \
  "feat(frontend): implement App state machine with conversation orchestration" \
  "Wires together message sending, optimistic UI updates, retry on failure,
feedback submission, 32-second AbortSignal timeout guard (matching the
backend 30s limit), and localStorage persistence for messages and
conversationId across page reloads and server restarts."


# ─── Commit 7 — FastAPI server ────────────────────────────────────────────── #

git add backend/main.py

commit \
  "feat(backend): bootstrap FastAPI server with rate limiting, CORS, and chat API" \
  "Configures FastAPI with slowapi rate limiting (10 req/min per IP on
/api/chat, 30/min on /api/feedback), CORS middleware restricted to
configured origins, Pydantic v2 request/response validation, in-process
conversation store capped at 12 messages per session, 30-second asyncio
timeout on LLM calls, and a /health liveness endpoint."


# ─── Commit 8 — Claude integration ────────────────────────────────────────── #

git add backend/llm_handler.py

commit \
  "feat(backend): integrate Anthropic SDK with grounded generation and caching" \
  "Implements LLMHandler using AsyncAnthropic with prompt caching
(cache_control: ephemeral) to reduce per-request latency on repeated
system prompt prefixes. Constructs the grounded system prompt, injects
retrieved KB sections as a structured <policy_context> XML block, and
estimates response confidence from KB hit count (0.60–0.92 range)."


# ─── Commit 9 — KB retrieval ──────────────────────────────────────────────── #

git add backend/knowledge_loader.py

commit \
  "feat(backend): implement Jaccard similarity search over markdown knowledge base" \
  "Parses knowledge_base.md into sections on ## / ### headings, tokenises
content (lowercased, stop words removed), and ranks sections by Jaccard
overlap with a 1.5x heading-match boost. Returns top-5 matching sections
as structured dicts injected into the LLM context window."


# ─── Commit 10 — Error handling + loading ─────────────────────────────────── #

git add \
  frontend/src/components/ErrorBoundary.tsx \
  frontend/src/components/LoadingSkeleton.tsx

commit \
  "feat(frontend): add ErrorBoundary and LoadingSkeleton for resilient UX" \
  "Wraps the app in a React class-based ErrorBoundary that catches unhandled
render exceptions and offers Try again / Reload page recovery controls.
Adds an accessible LoadingSkeleton (role=status, aria-label, aria-busy)
with a pulsing 4-line + 2-chip placeholder that replaces a plain spinner
while awaiting AI responses."


# ─── Commit 11 — Responsible AI docs ──────────────────────────────────────── #

git add RESPONSIBLE_AI.md

commit \
  "docs: add responsible AI documentation covering safety and governance" \
  "Documents intended use and prohibited uses, known system limitations
(static KB, no personalisation, hallucination risk), accuracy approach
(RAG confidence scoring, validation test suite), user feedback handling
process, HR escalation paths, production monitoring metrics and alert
thresholds, bias mitigation strategies, and data privacy controls."


# ─── Commit 12 — Architecture + README ────────────────────────────────────── #

git add README.md ARCHITECTURE.md PROMPT_DESIGN.md

commit \
  "docs: add architecture, prompt design, and developer README" \
  "ARCHITECTURE.md: full ASCII system diagram, step-by-step data flow,
React component tree, backend module responsibility table, scalability
path from single-process to Kubernetes, and guidance on handling larger
knowledge bases with dense embeddings.
PROMPT_DESIGN.md: system prompt with per-rule rationale, RAG retrieval
design, conversation history windowing strategy, Claude model selection
reasoning, and seven prompt engineering techniques.
README.md: quick-start guide, environment variable reference, and
two-terminal run instructions."


# ─── Commit 13 — Release v1.0.0 ───────────────────────────────────────────── #

git add COMMIT_GUIDE.md init_git_history.sh

commit \
  "release: v1.0.0 — complete HR Knowledge Copilot" \
  "Application is feature-complete: RAG-powered chat with Jaccard KB
retrieval, thumbs up/down feedback with optimistic UI, retry on error,
accessible loading skeleton, per-IP rate limiting, 30-second server
timeout, CORS, Anthropic prompt caching, in-process conversation history,
and a full responsible-AI and developer documentation suite."

git tag -a v1.0.0 -m "v1.0.0 — HR Knowledge Copilot initial release"


# ─── Summary ──────────────────────────────────────────────────────────────── #

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${GREEN}${BOLD}Done!${RESET} 13 commits created and tagged v1.0.0"
echo ""
git log --oneline
echo ""
echo -e "  Tag  : $(git describe --tags)"
echo -e "  Files: $(git diff-tree --no-commit-id -r HEAD --name-only | wc -l | tr -d ' ') in final commit"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  Next steps:"
echo "    git log --oneline          # review history"
echo "    git show <hash> --stat     # inspect any commit"
echo "    git diff HEAD~1 HEAD       # see what changed in last commit"
echo ""
