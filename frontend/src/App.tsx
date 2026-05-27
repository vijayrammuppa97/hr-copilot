import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, ChatRequest, ChatResponse, FeedbackRequest, FeedbackValue, SuggestedPrompt } from './types'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoadingSkeleton from './components/LoadingSkeleton'
import ErrorBoundary from './components/ErrorBoundary'

const STORAGE_KEY = 'hr_copilot_messages'
const CONVERSATION_ID_KEY = 'hr_copilot_conversation_id'
const API_BASE = import.meta.env.VITE_API_URL ?? ''

const SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  { label: 'Leave policy', query: 'What is the annual leave policy?' },
  { label: 'Remote work', query: 'How do I apply for remote work?' },
  { label: 'Benefits', query: 'What health benefits are available?' },
  { label: 'Escalation', query: 'How do I escalate a workplace concern?' },
]

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
}

function getOrCreateConversationId(): string {
  let id = localStorage.getItem(CONVERSATION_ID_KEY)
  if (!id) {
    id = generateId()
    localStorage.setItem(CONVERSATION_ID_KEY, id)
  }
  return id
}

function loadPersistedMessages(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed as Message[]
  } catch {
    return []
  }
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>(loadPersistedMessages)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const conversationId = useRef<string>(getOrCreateConversationId())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // Silently fail — storage quota may be exceeded
    }
  }, [messages])

  // Auto-scroll to latest message or skeleton
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Send message ─────────────────────────────────────────────────────── //

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim()
      if (!trimmed || isLoading) return

      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, userMessage])
      setIsLoading(true)
      setError(null)
      setLastFailedMessage(null)

      const body: ChatRequest = {
        message: trimmed,
        conversationId: conversationId.current,
      }

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          // Client-side guard to match the 30s server timeout
          signal: AbortSignal.timeout(32_000),
        })

        if (!res.ok) {
          let detail = `Server error ${res.status}`
          try {
            const errJson = (await res.json()) as { detail?: string }
            if (errJson.detail) detail = errJson.detail
          } catch {
            // response body may not be JSON
          }
          throw new Error(detail)
        }

        const data: ChatResponse = (await res.json()) as ChatResponse

        const assistantMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: data.message,
          sources: data.sources,
          confidence: data.confidence,
          timestamp: data.timestamp,
          feedback: null,
        }
        setMessages((prev) => [...prev, assistantMessage])
      } catch (err) {
        const isTimeout =
          err instanceof DOMException && err.name === 'TimeoutError'
        const msg = isTimeout
          ? 'The request timed out (>30 s). The AI service may be busy — please try again.'
          : err instanceof Error
          ? err.message
          : 'Unexpected error. Please try again.'

        setError(msg)
        setLastFailedMessage(trimmed)

        const errorMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: `I encountered an issue: ${msg}\n\nPlease try again or contact HR directly at hr@company.com.`,
          timestamp: new Date().toISOString(),
          isError: true,
        }
        setMessages((prev) => [...prev, errorMsg])
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading]
  )

  // ── Retry last failed message ────────────────────────────────────────── //

  const handleRetry = useCallback(() => {
    if (!lastFailedMessage) return
    setMessages((prev) => {
      const next = [...prev]
      // Remove the error assistant bubble
      if (next.at(-1)?.isError) next.pop()
      // Remove the original user message so sendMessage re-adds it cleanly
      if (next.at(-1)?.role === 'user') next.pop()
      return next
    })
    setError(null)
    const msg = lastFailedMessage
    setLastFailedMessage(null)
    void sendMessage(msg)
  }, [lastFailedMessage, sendMessage])

  // ── Feedback ─────────────────────────────────────────────────────────── //

  const handleFeedback = useCallback(
    async (messageId: string, value: FeedbackValue) => {
      // Optimistic UI update — no waiting for the server
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedback: value } : m))
      )

      const body: FeedbackRequest = {
        messageId,
        conversationId: conversationId.current,
        feedback: value,
      }

      try {
        await fetch(`${API_BASE}/api/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } catch {
        // Feedback is best-effort; don't surface errors to the user
      }
    },
    []
  )

  // ── Clear chat ───────────────────────────────────────────────────────── //

  const clearChat = useCallback(() => {
    setMessages([])
    setError(null)
    setLastFailedMessage(null)
    const newId = generateId()
    conversationId.current = newId
    localStorage.setItem(CONVERSATION_ID_KEY, newId)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen bg-gray-50">

        {/* ── Header ── */}
        <header className="bg-white border-b border-gray-200 shadow-sm z-10" role="banner">
          <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm flex-shrink-0"
                aria-hidden="true"
              >
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div className="min-w-0">
                <h1 className="text-base font-semibold text-gray-900 leading-tight truncate">
                  HR Knowledge Copilot
                </h1>
                <p className="text-xs text-gray-500">AI-powered policy assistant</p>
              </div>
            </div>

            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="ml-2 flex-shrink-0 px-3 py-1.5 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-400"
                aria-label="Clear all chat messages and start a new conversation"
              >
                Clear chat
              </button>
            )}
          </div>
        </header>

        {/* ── Message list ── */}
        <main
          className="flex-1 overflow-y-auto scrollbar-thin"
          role="main"
          aria-label="Chat conversation"
          aria-live="polite"
          aria-atomic="false"
          aria-relevant="additions"
        >
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">

            {/* ── Empty / welcome state ── */}
            {isEmpty && (
              <section className="text-center py-10" aria-labelledby="welcome-heading">
                <div
                  className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4"
                  aria-hidden="true"
                >
                  <svg className="w-7 h-7 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <h2 id="welcome-heading" className="text-lg font-semibold text-gray-900 mb-1">
                  How can I help you today?
                </h2>
                <p className="text-sm text-gray-500 mb-6 max-w-xs mx-auto">
                  Ask me about leave, remote work, benefits, onboarding, or any HR topic.
                </p>

                <nav aria-label="Suggested questions">
                  <ul className="grid grid-cols-2 gap-2 max-w-sm mx-auto list-none p-0">
                    {SUGGESTED_PROMPTS.map((p) => (
                      <li key={p.label}>
                        <button
                          onClick={() => void sendMessage(p.query)}
                          className="w-full px-3 py-2 text-sm text-left text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
                        >
                          {p.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                </nav>
              </section>
            )}

            {/* ── Messages ── */}
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onFeedback={handleFeedback}
                onRetry={msg.isError ? handleRetry : undefined}
              />
            ))}

            {/* ── Loading skeleton ── */}
            {isLoading && <LoadingSkeleton />}

            <div ref={messagesEndRef} aria-hidden="true" />
          </div>
        </main>

        {/* ── Error banner with retry ── */}
        {error && !isLoading && (
          <div
            className="bg-red-50 border-t border-red-200 px-4 py-2"
            role="alert"
            aria-live="assertive"
          >
            <div className="max-w-3xl mx-auto flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-sm text-red-700 flex-1 truncate">{error}</p>
              {lastFailedMessage && (
                <button
                  onClick={handleRetry}
                  className="flex-shrink-0 px-2.5 py-1 text-xs font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-red-400"
                  aria-label="Retry the failed message"
                >
                  Retry
                </button>
              )}
              <button
                onClick={() => setError(null)}
                className="flex-shrink-0 text-red-400 hover:text-red-600 focus:outline-none"
                aria-label="Dismiss error"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Input area ── */}
        <footer className="bg-white border-t border-gray-200">
          <div className="max-w-3xl mx-auto px-4 py-3">
            <ChatInput onSend={sendMessage} isLoading={isLoading} />
            <p className="text-xs text-gray-400 text-center mt-2">
              AI may make mistakes. Verify important decisions with HR directly.
            </p>
          </div>
        </footer>

      </div>
    </ErrorBoundary>
  )
}

export default App
