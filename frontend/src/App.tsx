import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, ChatRequest, OnboardingCase } from './types'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoadingSkeleton from './components/LoadingSkeleton'
import ErrorBoundary from './components/ErrorBoundary'
import Sidebar from './components/Sidebar'
import UserIdentityModal from './components/UserIdentityModal'
import EscalationModal from './components/EscalationModal'

const STORAGE_KEY        = 'hr_copilot_messages'
const CONVERSATION_ID_KEY = 'hr_copilot_conversation_id'
const CASE_ID_KEY         = 'hr_copilot_case_id'
const API_BASE            = import.meta.env.VITE_API_URL ?? ''

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

function buildWelcomeMessage(case_: OnboardingCase): Message {
  const firstName  = case_.employee_name.split(' ')[0]
  const stageName  = case_.workflow.find((s) => s.stage_id === case_.current_stage)?.name ?? 'your first stage'
  const totalDone  = case_.workflow.reduce((s, st) => s + st.completed_items, 0)
  const totalItems = case_.workflow.reduce((s, st) => s + st.total_items, 0)
  const isReturning = totalDone > 0

  const content = isReturning
    ? `Welcome back, ${firstName}! You've completed ${totalDone} of ${totalItems} onboarding tasks so far. You're currently on **${stageName}**. Let's pick up where you left off — what would you like to work on?`
    : `Hi ${firstName}, welcome to Acme! 🎉 I'm your HR Onboarding Assistant and I'll guide you through every step of joining the team.\n\nYour Case ID is **${case_.case_id}** — keep this handy for any HR queries.\n\nYou have **7 stages** to complete, starting with **${stageName}**. I'll walk you through each one. Ready to get started?`

  return {
    id: generateId(),
    role: 'assistant',
    content,
    timestamp: new Date().toISOString(),
  }
}

interface UploadedFile {
  name: string
  sections: number
}

const App: React.FC = () => {
  const [messages, setMessages]                 = useState<Message[]>(loadPersistedMessages)
  const [isLoading, setIsLoading]               = useState(false)
  const [error, setError]                       = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const [uploadedFiles, setUploadedFiles]       = useState<UploadedFile[]>([])
  const [isUploading, setIsUploading]           = useState(false)
  const [prefill, setPrefill]                   = useState('')
  const [onboardingCase, setOnboardingCase]     = useState<OnboardingCase | null>(null)
  const [showIdentityModal, setShowIdentityModal] = useState(false)
  const [showEscalation, setShowEscalation]     = useState(false)
  const [caseLoading, setCaseLoading]           = useState(true)
  const conversationId = useRef<string>(getOrCreateConversationId())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Load case on mount ───────────────────────────────────────────────── //
  useEffect(() => {
    const storedCaseId = localStorage.getItem(CASE_ID_KEY)
    if (!storedCaseId) {
      setCaseLoading(false)
      setShowIdentityModal(true)
      return
    }
    fetch(`${API_BASE}/api/cases/${storedCaseId}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data: OnboardingCase | null) => {
        if (data) {
          setOnboardingCase(data)
          // Add welcome message if chat is empty
          if (loadPersistedMessages().length === 0) {
            const welcome = buildWelcomeMessage(data)
            setMessages([welcome])
          }
        } else {
          localStorage.removeItem(CASE_ID_KEY)
          setShowIdentityModal(true)
        }
      })
      .catch(() => {
        setCaseLoading(false)
        setShowIdentityModal(true)
      })
      .finally(() => setCaseLoading(false))
  }, [])

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)) } catch { /* quota */ }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Case created ─────────────────────────────────────────────────────── //
  const handleCaseCreated = useCallback((case_: OnboardingCase) => {
    localStorage.setItem(CASE_ID_KEY, case_.case_id)
    setOnboardingCase(case_)
    setShowIdentityModal(false)
    const welcome = buildWelcomeMessage(case_)
    setMessages([welcome])
  }, [])

  // ── Refresh case from backend ─────────────────────────────────────────── //
  const refreshCase = useCallback(async (caseId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/cases/${caseId}`)
      if (res.ok) {
        const data = (await res.json()) as OnboardingCase
        setOnboardingCase(data)
      }
    } catch { /* best-effort */ }
  }, [])

  // ── Complete checklist item ────────────────────────────────────────────── //
  const handleCompleteItem = useCallback(async (stageId: string, itemId: string) => {
    if (!onboardingCase) return
    try {
      const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/complete-item`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage_id: stageId, item_id: itemId }),
      })
      if (res.ok) {
        const updated = (await res.json()) as OnboardingCase
        setOnboardingCase(updated)
        // Let the bot acknowledge it
        const stage = updated.workflow.find((s) => s.stage_id === stageId)
        const item  = stage?.items.find((i) => i.id === itemId)
        if (item) {
          void sendMessage(`I've marked "${item.label}" as complete.`)
        }
      }
    } catch { /* best-effort */ }
  }, [onboardingCase]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Advance stage ─────────────────────────────────────────────────────── //
  const handleAdvanceStage = useCallback(async () => {
    if (!onboardingCase) return
    try {
      const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/advance-stage`, {
        method: 'POST',
      })
      if (res.ok) {
        const updated = (await res.json()) as OnboardingCase
        setOnboardingCase(updated)
        const nextStage = updated.workflow.find((s) => s.stage_id === updated.current_stage)
        const msg = updated.status === 'completed'
          ? "I've completed all onboarding stages! What else can I help with?"
          : `Great — I'm ready to move on to **${nextStage?.name ?? 'the next stage'}**. What should we tackle first?`
        void sendMessage(msg)
      }
    } catch { /* best-effort */ }
  }, [onboardingCase]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stage click in sidebar ────────────────────────────────────────────── //
  const handleStageClick = useCallback((_stageId: string, stageName: string) => {
    setPrefill(`Tell me about the ${stageName} stage and what I need to do.`)
  }, [])

  // ── Escalation ───────────────────────────────────────────────────────── //
  const handleEscalated = useCallback((message: string) => {
    setShowEscalation(false)
    if (onboardingCase) void refreshCase(onboardingCase.case_id)
    setMessages((prev) => [...prev, {
      id: generateId(),
      role: 'assistant',
      content: message,
      timestamp: new Date().toISOString(),
    }])
  }, [onboardingCase, refreshCase])

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

    const body: ChatRequest = {
      message: trimmed,
      conversationId: conversationId.current,
      caseId: onboardingCase?.case_id,
    }

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

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body')

      setIsLoading(false)
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
        content: `Unable to get a response: ${msg}\n\nFor immediate help, contact HR at hr@acme.com or use the **Get Human Help** button.`,
        timestamp: new Date().toISOString(), isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, onboardingCase])

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
      setError(isTimeout ? 'Upload timed out.' : 'Upload failed. Is the backend running?')
    } finally {
      setIsUploading(false)
    }
  }, [])

  // ── Clear chat ────────────────────────────────────────────────────────── //
  const clearChat = useCallback(() => {
    setMessages([])
    setError(null)
    setLastFailedMessage(null)
    const newId = generateId()
    conversationId.current = newId
    localStorage.setItem(CONVERSATION_ID_KEY, newId)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  if (caseLoading) {
    return (
      <div className="flex h-screen bg-surface-base items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="w-6 h-6 text-indigo-400 animate-spin-slow" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm text-slate-500">Loading your onboarding…</p>
        </div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-surface-base overflow-hidden font-sans">

        {/* ── Identity modal ── */}
        {showIdentityModal && (
          <UserIdentityModal apiBase={API_BASE} onCaseCreated={handleCaseCreated} />
        )}

        {/* ── Escalation modal ── */}
        {showEscalation && onboardingCase && (
          <EscalationModal
            caseId={onboardingCase.case_id}
            apiBase={API_BASE}
            onClose={() => setShowEscalation(false)}
            onEscalated={handleEscalated}
          />
        )}

        {/* ── Left Sidebar ── */}
        <div className="hidden lg:flex">
          <Sidebar
            onNewChat={clearChat}
            case_={onboardingCase}
            onStageClick={handleStageClick}
            onCompleteItem={handleCompleteItem}
            onEscalate={() => setShowEscalation(true)}
            onAdvanceStage={handleAdvanceStage}
            uploadedFiles={uploadedFiles}
            onUpload={(f) => void handleFileUpload(f)}
            isUploading={isUploading}
          />
        </div>

        {/* ── Main chat panel ── */}
        <div className="flex-1 flex flex-col min-w-0">

          {/* Mobile header */}
          <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-surface-panel">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
                <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <span className="text-sm font-semibold text-slate-200">HR Onboarding</span>
                {onboardingCase && (
                  <span className="ml-2 text-[10px] text-slate-600 font-mono">{onboardingCase.case_id}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {onboardingCase && (
                <button
                  onClick={() => setShowEscalation(true)}
                  className="text-xs text-amber-500 hover:text-amber-300 transition-colors"
                >
                  Get Help
                </button>
              )}
              {messages.length > 0 && (
                <button onClick={clearChat} className="text-xs text-slate-600 hover:text-slate-400 transition-colors">
                  Clear
                </button>
              )}
            </div>
          </header>

          {/* Stage banner (shows current stage name on mobile) */}
          {onboardingCase && (
            <div className="lg:hidden flex items-center gap-2 px-4 py-2 bg-indigo-500/[0.07] border-b border-indigo-500/[0.12]">
              {(() => {
                const stage = onboardingCase.workflow.find((s) => s.stage_id === onboardingCase.current_stage)
                return stage ? (
                  <>
                    <span className="text-base">{stage.icon}</span>
                    <span className="text-xs text-indigo-300 font-medium">{stage.name}</span>
                    <span className="text-[10px] text-slate-600 ml-auto">{stage.completed_items}/{stage.total_items}</span>
                  </>
                ) : null
              })()}
            </div>
          )}

          {/* Messages */}
          <main className="flex-1 overflow-y-auto scrollbar-dark" role="main" aria-label="Chat conversation" aria-live="polite" aria-atomic="false" aria-relevant="additions">
            <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} onRetry={msg.isError ? handleRetry : undefined} />
              ))}
              {isLoading && <LoadingSkeleton />}
              <div ref={messagesEndRef} aria-hidden="true" />
            </div>
          </main>

          {/* Error banner */}
          {error && !isLoading && (
            <div className="border-t border-rose-500/[0.15] bg-rose-950/30 px-6 py-2.5" role="alert" aria-live="assertive">
              <div className="max-w-3xl mx-auto flex items-center gap-2.5">
                <svg className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-xs text-rose-300 flex-1 truncate">{error}</p>
                {lastFailedMessage && (
                  <button onClick={handleRetry} className="flex-shrink-0 px-2.5 py-1 text-xs font-medium text-rose-300 bg-rose-500/[0.12] hover:bg-rose-500/20 border border-rose-500/25 rounded-md transition-all">
                    Retry
                  </button>
                )}
                <button onClick={() => setError(null)} className="flex-shrink-0 text-rose-600 hover:text-rose-400 transition-colors" aria-label="Dismiss error">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Input composer */}
          <footer className="border-t border-white/[0.06] bg-surface-base/80 backdrop-blur-xs px-6 py-4">
            <div className="max-w-3xl mx-auto">
              <ChatInput
                onSend={sendMessage}
                isLoading={isLoading}
                prefill={prefill}
                onPrefillConsumed={() => setPrefill('')}
              />
              <p className="text-[10px] text-slate-700 text-center mt-2.5">
                AI responses are grounded in your onboarding context and Acme HR policy. Verify important decisions with HR directly.
              </p>
            </div>
          </footer>

        </div>
      </div>
    </ErrorBoundary>
  )
}

export default App
