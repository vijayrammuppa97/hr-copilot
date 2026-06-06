import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, ChatRequest, OnboardingCase } from './types'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import LoadingSkeleton from './components/LoadingSkeleton'
import ErrorBoundary from './components/ErrorBoundary'
import Sidebar from './components/Sidebar'
import EscalationModal from './components/EscalationModal'
import AdminDashboard from './components/AdminDashboard'

const STORAGE_KEY         = 'hr_copilot_messages'
const CONVERSATION_ID_KEY = 'hr_copilot_conversation_id'
const CASE_ID_KEY         = 'hr_copilot_case_id'
const USER_ID_KEY         = 'hr_copilot_user_id'
const USERNAME_KEY        = 'hr_copilot_username'
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
    ? `Welcome back, ${firstName}! You've completed ${totalDone} of ${totalItems} onboarding tasks. Currently on **${stageName}** — let's pick up where you left off.`
    : `Hi ${firstName}, welcome to Acme! I'm your HR Onboarding Assistant.\n\nYour Case ID is **${case_.case_id}** — keep this for any HR queries. You have **7 stages** to complete, starting with **${stageName}**. Ready to get started?`
  return { id: generateId(), role: 'assistant', content, timestamp: new Date().toISOString() }
}

interface UploadedFile { name: string; sections: number }

interface UserSession {
  session_id: string
  started_at: string
  updated_at: string
  message_count: number
  preview: string | null
}

const App: React.FC = () => {
  const [messages, setMessages]                   = useState<Message[]>(loadPersistedMessages)
  const [isLoading, setIsLoading]                 = useState(false)
  const [error, setError]                         = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const [uploadedFiles, setUploadedFiles]         = useState<UploadedFile[]>([])
  const [isUploading, setIsUploading]             = useState(false)
  const [prefill, setPrefill]                     = useState('')
  const [onboardingCase, setOnboardingCase]       = useState<OnboardingCase | null>(null)
  const [showEscalation, setShowEscalation]       = useState(false)
  const [showAdmin, setShowAdmin]                 = useState(false)
  const [caseLoading, setCaseLoading]             = useState(true)
  const [userId, setUserId]                       = useState<string>('')
  const [username, setUsername]                   = useState<string>('')
  const [userSessions, setUserSessions]           = useState<UserSession[]>([])
  const conversationId = useRef<string>(getOrCreateConversationId())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Register / restore user on mount ─────────────────────────────────── //
  useEffect(() => {
    const storedId   = localStorage.getItem(USER_ID_KEY)   ?? ''
    const storedName = localStorage.getItem(USERNAME_KEY)  ?? ''

    fetch(`${API_BASE}/api/users/register`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ user_id: storedId || undefined, username: storedName || undefined }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data: { user_id: string; username: string } | null) => {
        if (data) {
          setUserId(data.user_id)
          setUsername(data.username)
          localStorage.setItem(USER_ID_KEY,  data.user_id)
          localStorage.setItem(USERNAME_KEY, data.username)
          // Load session history
          return fetch(`${API_BASE}/api/users/${data.user_id}/sessions`)
            .then((r) => r.ok ? r.json() : [])
            .then((sessions: UserSession[]) => setUserSessions(sessions))
        }
      })
      .catch(() => { /* best-effort */ })
  }, [])

  // ── Load case on mount ───────────────────────────────────────────────── //
  useEffect(() => {
    const storedCaseId = localStorage.getItem(CASE_ID_KEY)
    if (!storedCaseId) { setCaseLoading(false); return }
    fetch(`${API_BASE}/api/cases/${storedCaseId}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data: OnboardingCase | null) => {
        if (data) {
          setOnboardingCase(data)
          if (loadPersistedMessages().length === 0) setMessages([buildWelcomeMessage(data)])
        } else {
          localStorage.removeItem(CASE_ID_KEY)
        }
      })
      .catch(() => { /* general HR mode */ })
      .finally(() => setCaseLoading(false))
  }, [])

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)) } catch { /* quota */ }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Refresh case ─────────────────────────────────────────────────────── //
  const refreshCase = useCallback(async (caseId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/cases/${caseId}`)
      if (res.ok) setOnboardingCase((await res.json()) as OnboardingCase)
    } catch { /* best-effort */ }
  }, [])

  // ── Complete checklist item ───────────────────────────────────────────── //
  const handleCompleteItem = useCallback(async (stageId: string, itemId: string) => {
    if (!onboardingCase) return
    const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/complete-item`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ stage_id: stageId, item_id: itemId }),
    }).catch(() => null)
    if (res?.ok) {
      const updated = (await res.json()) as OnboardingCase
      setOnboardingCase(updated)
      const stage = updated.workflow.find((s) => s.stage_id === stageId)
      const item  = stage?.items.find((i) => i.id === itemId)
      if (item) void sendMessage(`I've marked "${item.label}" as complete.`)
    }
  }, [onboardingCase]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Advance stage ─────────────────────────────────────────────────────── //
  const handleAdvanceStage = useCallback(async () => {
    if (!onboardingCase) return
    const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/advance-stage`, { method: 'POST' }).catch(() => null)
    if (res?.ok) {
      const updated = (await res.json()) as OnboardingCase
      setOnboardingCase(updated)
      const nextStage = updated.workflow.find((s) => s.stage_id === updated.current_stage)
      const msg = updated.status === 'completed'
        ? "I've completed all onboarding stages! What else can I help with?"
        : `Moving on to **${nextStage?.name ?? 'the next stage'}** — what would you like to tackle first?`
      void sendMessage(msg)
    }
  }, [onboardingCase]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stage click ───────────────────────────────────────────────────────── //
  const handleStageClick = useCallback((_stageId: string, stageName: string) => {
    setPrefill(`Tell me about the ${stageName} stage and what I need to do.`)
  }, [])

  // ── Escalation ────────────────────────────────────────────────────────── //
  const handleEscalated = useCallback((message: string) => {
    setShowEscalation(false)
    if (onboardingCase) void refreshCase(onboardingCase.case_id)
    setMessages((prev) => [...prev, { id: generateId(), role: 'assistant', content: message, timestamp: new Date().toISOString() }])
  }, [onboardingCase, refreshCase])

  // ── Send ──────────────────────────────────────────────────────────────── //
  const sendMessage = useCallback(async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || isLoading) return

    setMessages((prev) => [...prev, { id: generateId(), role: 'user', content: trimmed, timestamp: new Date().toISOString() }])
    setIsLoading(true)
    setError(null)
    setLastFailedMessage(null)

    const body: ChatRequest = {
      message:        trimmed,
      conversationId: conversationId.current,
      caseId:         onboardingCase?.case_id,
      userId:         userId || undefined,
    } as ChatRequest & { userId?: string }

    const assistantId = generateId()

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
        signal:  AbortSignal.timeout(125_000),
      })
      if (!res.ok) {
        let detail = `Server error ${res.status}`
        try { const j = (await res.json()) as { detail?: string }; if (j.detail) detail = j.detail } catch { /* ok */ }
        throw new Error(detail)
      }

      const reader  = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body')

      setIsLoading(false)
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '', sources: [], confidence: 0, timestamp: new Date().toISOString(), feedback: null }])

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
            const evt = JSON.parse(line.slice(6)) as { type: string; text?: string; sources?: string[]; confidence?: number; follow_up_questions?: string[]; timestamp?: string; message?: string }
            if (evt.type === 'token' && evt.text) {
              setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content + evt.text } : m))
            } else if (evt.type === 'done') {
              setMessages((prev) => prev.map((m) => m.id === assistantId ? {
                ...m,
                sources: evt.sources ?? [],
                confidence: evt.confidence ?? 0,
                followUpQuestions: evt.follow_up_questions ?? [],
                timestamp: evt.timestamp ?? m.timestamp,
              } : m))
            } else if (evt.type === 'error') {
              throw new Error(evt.message ?? 'Stream error')
            }
          } catch { /* malformed */ }
        }
      }
      return
    } catch (err) {
      const isTimeout = err instanceof DOMException && err.name === 'TimeoutError'
      const msg = isTimeout
        ? 'Request timed out. Ollama may still be loading the model — please try again.'
        : err instanceof Error ? err.message : 'Unexpected error.'
      setError(msg)
      setLastFailedMessage(trimmed)
      setMessages((prev) => [...prev, { id: generateId(), role: 'assistant', content: `Unable to get a response: ${msg}\n\nUse the **Get Human Help** button for immediate assistance.`, timestamp: new Date().toISOString(), isError: true }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, onboardingCase, userId])

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

  const handleFileUpload = useCallback(async (file: File) => {
    setIsUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData, signal: AbortSignal.timeout(30_000) })
      if (!res.ok) { const j = (await res.json()) as { detail?: string }; setError(j.detail ?? 'Upload failed'); return }
      const data = (await res.json()) as { filename: string; sections_added: number }
      setUploadedFiles((prev) => {
        const exists = prev.find((f) => f.name === data.filename)
        if (exists) return prev.map((f) => f.name === data.filename ? { ...f, sections: f.sections + data.sections_added } : f)
        return [...prev, { name: data.filename, sections: data.sections_added }]
      })
    } catch { setError('Upload failed. Is the backend running?') }
    finally { setIsUploading(false) }
  }, [])

  const clearChat = useCallback(() => {
    setMessages([]); setError(null); setLastFailedMessage(null)
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
          <p className="text-sm text-slate-500">Loading your workspace…</p>
        </div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-surface-base overflow-hidden font-sans">

        {showEscalation && onboardingCase && (
          <EscalationModal caseId={onboardingCase.case_id} apiBase={API_BASE} onClose={() => setShowEscalation(false)} onEscalated={handleEscalated} />
        )}

        {showAdmin && <AdminDashboard onClose={() => setShowAdmin(false)} />}

        {/* Sidebar */}
        <div className="hidden lg:flex">
          <Sidebar
            onNewChat={clearChat}
            case_={onboardingCase}
            onStageClick={handleStageClick}
            onCompleteItem={handleCompleteItem}
            onEscalate={() => setShowEscalation(true)}
            onAdvanceStage={handleAdvanceStage}
            onOpenAdmin={() => setShowAdmin(true)}
            uploadedFiles={uploadedFiles}
            onUpload={(f) => void handleFileUpload(f)}
            isUploading={isUploading}
            username={username}
            userSessions={userSessions}
            activeSessionId={conversationId.current}
            onSelectSession={(sid) => {
              conversationId.current = sid
              localStorage.setItem(CONVERSATION_ID_KEY, sid)
              setMessages([])
              localStorage.removeItem(STORAGE_KEY)
            }}
          />
        </div>

        {/* Main panel */}
        <div className="flex-1 flex flex-col min-w-0">
          <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-surface-panel">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
                <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-slate-200">HR Onboarding</span>
            </div>
            <div className="flex items-center gap-2">
              {onboardingCase && <button onClick={() => setShowEscalation(true)} className="text-xs text-amber-500">Get Help</button>}
              {messages.length > 0 && <button onClick={clearChat} className="text-xs text-slate-600 hover:text-slate-400">Clear</button>}
            </div>
          </header>

          {/* Username badge */}
          {username && (
            <div className="lg:hidden flex items-center gap-2 px-4 py-1.5 bg-surface-panel border-b border-white/[0.04]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-[10px] text-slate-600 font-mono">{username}</span>
            </div>
          )}

          <main className="flex-1 overflow-y-auto scrollbar-dark" role="main" aria-live="polite" aria-atomic="false" aria-relevant="additions">
            <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onRetry={msg.isError ? handleRetry : undefined}
                  onFollowUp={(q) => void sendMessage(q)}
                />
              ))}
              {isLoading && <LoadingSkeleton />}
              <div ref={messagesEndRef} aria-hidden="true" />
            </div>
          </main>

          {error && !isLoading && (
            <div className="border-t border-rose-500/[0.15] bg-rose-950/30 px-6 py-2.5" role="alert">
              <div className="max-w-3xl mx-auto flex items-center gap-2.5">
                <p className="text-xs text-rose-300 flex-1 truncate">{error}</p>
                {lastFailedMessage && (
                  <button onClick={handleRetry} className="flex-shrink-0 px-2.5 py-1 text-xs font-medium text-rose-300 bg-rose-500/[0.12] hover:bg-rose-500/20 border border-rose-500/25 rounded-md transition-all">Retry</button>
                )}
                <button onClick={() => setError(null)} className="flex-shrink-0 text-rose-600 hover:text-rose-400" aria-label="Dismiss">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
            </div>
          )}

          <footer className="border-t border-white/[0.06] bg-surface-base/80 backdrop-blur-xs px-6 py-4">
            <div className="max-w-3xl mx-auto">
              <ChatInput onSend={sendMessage} isLoading={isLoading} prefill={prefill} onPrefillConsumed={() => setPrefill('')} />
              <p className="text-[10px] text-slate-700 text-center mt-2.5">
                Responses are grounded in HR policy and your onboarding context. Verify important decisions with HR directly.
              </p>
            </div>
          </footer>
        </div>
      </div>
    </ErrorBoundary>
  )
}

export default App
