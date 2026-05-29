import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, ChatRequest, ChatResponse, FeedbackValue } from './types'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoadingSkeleton from './components/LoadingSkeleton'
import ErrorBoundary from './components/ErrorBoundary'
import Sidebar from './components/Sidebar'

const STORAGE_KEY        = 'hr_copilot_messages'
const CONVERSATION_ID_KEY = 'hr_copilot_conversation_id'
const API_BASE           = import.meta.env.VITE_API_URL ?? ''

const WELCOME_PROMPTS = [
  {
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
    label:       'Leave & Time Off',
    description: 'Annual leave, sick days, parental & emergency leave',
    query:       'What is the annual leave entitlement policy?',
    accent:      'text-sky-400',
    iconBg:      'bg-sky-400/[0.12] border-sky-400/20',
    hoverBorder: 'hover:border-sky-500/30 hover:bg-sky-500/[0.05]',
  },
  {
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
    label:       'Remote Work',
    description: 'WFH eligibility, hybrid schedules, international work',
    query:       'What is the remote work and work from home policy?',
    accent:      'text-violet-400',
    iconBg:      'bg-violet-400/[0.12] border-violet-400/20',
    hoverBorder: 'hover:border-violet-500/30 hover:bg-violet-500/[0.05]',
  },
  {
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    ),
    label:       'Benefits',
    description: 'Health insurance, 401k match, dental, vision & perks',
    query:       'What employee benefits does the company offer?',
    accent:      'text-emerald-400',
    iconBg:      'bg-emerald-400/[0.12] border-emerald-400/20',
    hoverBorder: 'hover:border-emerald-500/30 hover:bg-emerald-500/[0.05]',
  },
  {
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
    label:       'Onboarding',
    description: 'First day checklist, buddy program, equipment setup',
    query:       'What does the onboarding process look like?',
    accent:      'text-amber-400',
    iconBg:      'bg-amber-400/[0.12] border-amber-400/20',
    hoverBorder: 'hover:border-amber-500/30 hover:bg-amber-500/[0.05]',
  },
]

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
}

function getOrCreateConversationId(): string {
  let id = localStorage.getItem(CONVERSATION_ID_KEY)
  if (!id) { id = generateId(); localStorage.setItem(CONVERSATION_ID_KEY, id) }
  return id
}

function loadPersistedMessages(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Message[]) : []
  } catch { return [] }
}

interface UploadedFile {
  name: string
  sections: number
}

const App: React.FC = () => {
  const [messages, setMessages]               = useState<Message[]>(loadPersistedMessages)
  const [isLoading, setIsLoading]             = useState(false)
  const [error, setError]                     = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const [uploadedFiles, setUploadedFiles]     = useState<UploadedFile[]>([])
  const [isUploading, setIsUploading]         = useState(false)
  const conversationId = useRef<string>(getOrCreateConversationId())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)) } catch { /* quota */ }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Send ──────────────────────────────────────────────────────────────── //
  const sendMessage = useCallback(async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || isLoading) return

    setMessages((prev) => [...prev, {
      id: generateId(), role: 'user', content: trimmed,
      timestamp: new Date().toISOString(),
    }])
    setIsLoading(true)
    setError(null)
    setLastFailedMessage(null)

    const body: ChatRequest = { message: trimmed, conversationId: conversationId.current }

    const assistantId = generateId()

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(125_000),
      })
      if (!res.ok) {
        let detail = `Server error ${res.status}`
        try { const j = (await res.json()) as { detail?: string }; if (j.detail) detail = j.detail } catch { /* ok */ }
        throw new Error(detail)
      }

      // Stream tokens as they arrive
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body')

      setIsLoading(false) // hide skeleton — streaming starts now
      setMessages((prev) => [...prev, {
        id: assistantId, role: 'assistant', content: '', sources: [],
        confidence: 0, timestamp: new Date().toISOString(), feedback: null,
      }])

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6)) as { type: string; text?: string; sources?: string[]; confidence?: number; timestamp?: string; message?: string }
            if (evt.type === 'token' && evt.text) {
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + evt.text } : m
              ))
            } else if (evt.type === 'done') {
              setMessages((prev) => prev.map((m) =>
                m.id === assistantId ? { ...m, sources: evt.sources ?? [], confidence: evt.confidence ?? 0, timestamp: evt.timestamp ?? m.timestamp } : m
              ))
            } else if (evt.type === 'error') {
              throw new Error(evt.message ?? 'Stream error')
            }
          } catch { /* malformed line */ }
        }
      }
      return
    } catch (err) {
      const isTimeout = err instanceof DOMException && err.name === 'TimeoutError'
      const msg = isTimeout
        ? 'Request timed out. Ollama may still be loading the model — please try again.'
        : err instanceof Error ? err.message : 'Unexpected error. Please try again.'
      setError(msg)
      setLastFailedMessage(trimmed)
      setMessages((prev) => [...prev, {
        id: generateId(), role: 'assistant',
        content: `Unable to get a response: ${msg}\n\nFor immediate help, contact HR at hr@acme.com.`,
        timestamp: new Date().toISOString(), isError: true,
      }])
    } finally {
      setIsLoading(false)  // no-op if already cleared during streaming
    }
  }, [isLoading])

  // ── Retry ─────────────────────────────────────────────────────────────── //
  const handleRetry = useCallback(() => {
    if (!lastFailedMessage) return
    setMessages((prev) => {
      const next = [...prev]
      if (next.at(-1)?.isError) next.pop()
      if (next.at(-1)?.role === 'user') next.pop()
      return next
    })
    setError(null)
    const msg = lastFailedMessage
    setLastFailedMessage(null)
    void sendMessage(msg)
  }, [lastFailedMessage, sendMessage])

  // ── Feedback ──────────────────────────────────────────────────────────── //
  const handleFeedback = useCallback(async (messageId: string, value: FeedbackValue) => {
    setMessages((prev) => prev.map((m) => m.id === messageId ? { ...m, feedback: value } : m))
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messageId, conversationId: conversationId.current, feedback: value }),
      })
    } catch { /* best-effort */ }
  }, [])

  // ── Upload ────────────────────────────────────────────────────────────── //
  const handleFileUpload = useCallback(async (file: File) => {
    setIsUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(30_000),
      })
      if (!res.ok) {
        let detail = `Upload failed (${res.status})`
        try { const j = (await res.json()) as { detail?: string }; if (j.detail) detail = j.detail } catch { /* ok */ }
        setError(detail)
        return
      }
      const data = (await res.json()) as { filename: string; sections_added: number }
      setUploadedFiles((prev) => {
        const exists = prev.find((f) => f.name === data.filename)
        if (exists) return prev.map((f) => f.name === data.filename ? { ...f, sections: f.sections + data.sections_added } : f)
        return [...prev, { name: data.filename, sections: data.sections_added }]
      })
    } catch (err) {
      const isTimeout = err instanceof DOMException && err.name === 'TimeoutError'
      setError(isTimeout ? 'Upload timed out. Try a smaller file.' : 'Upload failed. Is the backend running?')
    } finally {
      setIsUploading(false)
    }
  }, [])

  // ── Clear ─────────────────────────────────────────────────────────────── //
  const clearChat = useCallback(() => {
    setMessages([]); setError(null); setLastFailedMessage(null)
    const newId = generateId()
    conversationId.current = newId
    localStorage.setItem(CONVERSATION_ID_KEY, newId)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  const isEmpty = messages.length === 0 && !isLoading
  const conversationPreview = messages.find((m) => m.role === 'user')?.content ?? ''

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-surface-base overflow-hidden font-sans">

        {/* ── Left Sidebar ── */}
        <div className="hidden lg:flex">
          <Sidebar
            onNewChat={clearChat}
            onPromptSelect={(q) => void sendMessage(q)}
            hasMessages={messages.length > 0}
            conversationPreview={conversationPreview}
            uploadedFiles={uploadedFiles}
            onUpload={(f) => void handleFileUpload(f)}
            isUploading={isUploading}
          />
        </div>

        {/* ── Main Panel ── */}
        <div className="flex-1 flex flex-col min-w-0">

          {/* Mobile header */}
          <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-surface-panel">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
                <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-slate-200">Acme HR Copilot</span>
            </div>
            {messages.length > 0 && (
              <button onClick={clearChat} className="text-xs text-slate-600 hover:text-slate-400 transition-colors">
                Clear
              </button>
            )}
          </header>

          {/* Messages */}
          <main
            className="flex-1 overflow-y-auto scrollbar-dark"
            role="main"
            aria-label="Chat conversation"
            aria-live="polite"
            aria-atomic="false"
            aria-relevant="additions"
          >
            <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">

              {/* ── Welcome state ── */}
              {isEmpty && (
                <section className="animate-fade-in" aria-labelledby="welcome-heading">
                  <div className="text-center mb-10">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-600/[0.15] border border-indigo-500/25 flex items-center justify-center mx-auto mb-5">
                      <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    </div>
                    <h1 id="welcome-heading" className="text-2xl font-semibold text-slate-100 mb-2 tracking-tight">
                      HR Knowledge Copilot
                    </h1>
                    <p className="text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
                      Your AI-powered HR knowledge system. Ask about policies, benefits, leave, or any HR topic.
                    </p>
                  </div>

                  <nav aria-label="Suggested topics">
                    <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-3 text-center">Quick start</p>
                    <ul className="grid grid-cols-2 gap-3 max-w-2xl mx-auto list-none p-0 m-0">
                      {WELCOME_PROMPTS.map((p) => (
                        <li key={p.label}>
                          <button
                            onClick={() => void sendMessage(p.query)}
                            className={`w-full flex items-start gap-3 p-4 rounded-xl bg-surface-card border border-white/[0.07] ${p.hoverBorder} transition-all duration-200 text-left group hover:scale-[1.01] active:scale-[0.99]`}
                          >
                            <div className={`w-8 h-8 rounded-lg border flex items-center justify-center flex-shrink-0 ${p.iconBg} ${p.accent} transition-transform group-hover:scale-105`}>
                              {p.icon}
                            </div>
                            <div className="min-w-0">
                              <p className={`text-[13px] font-medium text-slate-300 group-hover:${p.accent} transition-colors leading-snug`}>
                                {p.label}
                              </p>
                              <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">{p.description}</p>
                            </div>
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
                  onRetry={msg.isError ? handleRetry : undefined}
                />
              ))}

              {isLoading && <LoadingSkeleton />}

              <div ref={messagesEndRef} aria-hidden="true" />
            </div>
          </main>

          {/* ── Error banner ── */}
          {error && !isLoading && (
            <div
              className="border-t border-rose-500/[0.15] bg-rose-950/30 px-6 py-2.5"
              role="alert"
              aria-live="assertive"
            >
              <div className="max-w-3xl mx-auto flex items-center gap-2.5">
                <svg className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-xs text-rose-300 flex-1 truncate">{error}</p>
                {lastFailedMessage && (
                  <button
                    onClick={handleRetry}
                    className="flex-shrink-0 px-2.5 py-1 text-xs font-medium text-rose-300 bg-rose-500/[0.12] hover:bg-rose-500/20 border border-rose-500/25 rounded-md transition-all"
                  >
                    Retry
                  </button>
                )}
                <button
                  onClick={() => setError(null)}
                  className="flex-shrink-0 text-rose-600 hover:text-rose-400 transition-colors focus:outline-none"
                  aria-label="Dismiss error"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* ── Input composer ── */}
          <footer className="border-t border-white/[0.06] bg-surface-base/80 backdrop-blur-xs px-6 py-4">
            <div className="max-w-3xl mx-auto">
              <ChatInput onSend={sendMessage} isLoading={isLoading} />
              <p className="text-[10px] text-slate-700 text-center mt-2.5">
                AI responses are grounded in Acme HR policy only. Verify important decisions with HR directly.
              </p>
            </div>
          </footer>
        </div>

      </div>
    </ErrorBoundary>
  )
}

export default App
