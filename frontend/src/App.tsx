import React, { useEffect, useRef, useCallback, useState } from 'react'

// ── Hooks ─────────────────────────────────────────────────────────────────── //
import { useAuth }        from './hooks/useAuth'
import { useUserProfile } from './hooks/useUserProfile'
import { useChat }        from './hooks/useChat'

// ── Components ────────────────────────────────────────────────────────────── //
import {
  AuthPage, ChatMessage, ChatInput, LoadingSkeleton,
  ErrorBoundary, Sidebar, EscalationModal, AdminDashboard,
} from './components'

// ── Types ─────────────────────────────────────────────────────────────────── //
import type { OnboardingCase } from './types'

// ── Constants ─────────────────────────────────────────────────────────────── //
import { API_BASE, CASE_ID_KEY } from './constants'

// ── App ───────────────────────────────────────────────────────────────────── //

const App: React.FC = () => {
  // Auth
  const { authUser, authChecked, isAdmin, handleAuth, handleLogout } = useAuth()

  // User profile — re-fetches when account switches
  const {
    userId, username, userSessions, userProfile, setUserProfile, clearUserState,
  } = useUserProfile(authUser?.user_id)

  // Chat
  const {
    messages, isLoading, error, lastFailedMessage, isUploading,
    conversationId, sendMessage, handleRetry, handleFileUpload, clearChat,
    setMessages, setError,
  } = useChat()

  // UI state
  const [prefill,        setPrefill]        = useState('')
  const [onboardingCase, setOnboardingCase] = useState<OnboardingCase | null>(null)
  const [showEscalation, setShowEscalation] = useState(false)
  const [showAdmin,      setShowAdmin]      = useState(false)
  const [caseLoading,    setCaseLoading]    = useState(true)
  const [uploadedFiles,  setUploadedFiles]  = useState<{ name: string; sections: number }[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Load onboarding case ─────────────────────────────────────────────── //
  useEffect(() => {
    const storedCaseId = localStorage.getItem(CASE_ID_KEY)
    if (!storedCaseId) { setCaseLoading(false); return }
    fetch(`${API_BASE}/api/cases/${storedCaseId}`)
      .then(r => r.ok ? r.json() : null)
      .then((data: OnboardingCase | null) => {
        if (data) {
          setOnboardingCase(data)
          if (!messages.length) {
            const firstName = data.employee_name.split(' ')[0]
            const stageName = data.workflow.find(s => s.stage_id === data.current_stage)?.name ?? 'your first stage'
            const totalDone  = data.workflow.reduce((s, st) => s + st.completed_items, 0)
            const totalItems = data.workflow.reduce((s, st) => s + st.total_items, 0)
            const content = totalDone > 0
              ? `Welcome back, ${firstName}! You've completed ${totalDone} of ${totalItems} onboarding tasks. Currently on **${stageName}** — let's pick up where you left off.`
              : `Hi ${firstName}, welcome to Acme! I'm your HR Onboarding Assistant.\n\nYour Case ID is **${data.case_id}** — keep this for any HR queries. You have **7 stages** to complete, starting with **${stageName}**. Ready to get started?`
            setMessages([{ id: `${Date.now()}`, role: 'assistant', content, timestamp: new Date().toISOString() }])
          }
        } else {
          localStorage.removeItem(CASE_ID_KEY)
        }
      })
      .catch(() => {})
      .finally(() => setCaseLoading(false))
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Scroll to bottom ─────────────────────────────────────────────────── //
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Persist messages ─────────────────────────────────────────────────── //
  useEffect(() => {
    try { localStorage.setItem('hr_copilot_messages', JSON.stringify(messages)) } catch { /* quota */ }
  }, [messages])

  // ── Onboarding helpers ───────────────────────────────────────────────── //
  const refreshCase = useCallback(async (caseId: string) => {
    const res = await fetch(`${API_BASE}/api/cases/${caseId}`).catch(() => null)
    if (res?.ok) setOnboardingCase(await res.json() as OnboardingCase)
  }, [])

  const handleCompleteItem = useCallback(async (stageId: string, itemId: string) => {
    if (!onboardingCase) return
    const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/complete-item`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage_id: stageId, item_id: itemId }),
    }).catch(() => null)
    if (res?.ok) {
      const updated = await res.json() as OnboardingCase
      setOnboardingCase(updated)
      const item = updated.workflow.find(s => s.stage_id === stageId)?.items.find(i => i.id === itemId)
      if (item) void sendMessage(`I've marked "${item.label}" as complete.`, userId, onboardingCase.case_id)
    }
  }, [onboardingCase, sendMessage, userId])

  const handleAdvanceStage = useCallback(async () => {
    if (!onboardingCase) return
    const res = await fetch(`${API_BASE}/api/cases/${onboardingCase.case_id}/advance-stage`, { method: 'POST' }).catch(() => null)
    if (res?.ok) {
      const updated = await res.json() as OnboardingCase
      setOnboardingCase(updated)
      const nextStage = updated.workflow.find(s => s.stage_id === updated.current_stage)
      const msg = updated.status === 'completed'
        ? "I've completed all onboarding stages! What else can I help with?"
        : `Moving on to **${nextStage?.name ?? 'the next stage'}** — what would you like to tackle first?`
      void sendMessage(msg, userId, onboardingCase.case_id)
    }
  }, [onboardingCase, sendMessage, userId])

  const handleEscalated = useCallback((message: string) => {
    setShowEscalation(false)
    if (onboardingCase) void refreshCase(onboardingCase.case_id)
    setMessages(prev => [...prev, { id: `${Date.now()}`, role: 'assistant', content: message, timestamp: new Date().toISOString() }])
  }, [onboardingCase, refreshCase, setMessages])

  const handleLogoutFull = useCallback(() => {
    handleLogout()
    clearUserState()
    setMessages([])
    setError(null)
  }, [handleLogout, clearUserState, setMessages, setError])

  const handleUpload = useCallback(async (file: File) => {
    const result = await handleFileUpload(file)
    if (result) setUploadedFiles(prev => {
      const existing = prev.find(f => f.name === result.name)
      if (existing) return prev.map(f => f.name === result.name ? { ...f, sections: f.sections + result.sections } : f)
      return [...prev, result]
    })
  }, [handleFileUpload])

  // ── Auth gate ─────────────────────────────────────────────────────────── //
  if (!authChecked) {
    return (
      <div className="flex h-screen bg-surface-base items-center justify-center">
        <svg className="w-6 h-6 text-indigo-400 animate-spin-slow" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    )
  }

  if (!authUser) {
    return <ErrorBoundary><AuthPage onAuth={handleAuth} /></ErrorBoundary>
  }

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

  // ── Main layout ───────────────────────────────────────────────────────── //
  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-surface-base overflow-hidden font-sans">

        {showEscalation && onboardingCase && (
          <EscalationModal
            caseId={onboardingCase.case_id}
            apiBase={API_BASE}
            onClose={() => setShowEscalation(false)}
            onEscalated={handleEscalated}
          />
        )}

        {showAdmin && isAdmin && <AdminDashboard onClose={() => setShowAdmin(false)} />}

        {/* Sidebar */}
        <div className="hidden lg:flex">
          <Sidebar
            onNewChat={clearChat}
            case_={onboardingCase}
            onStageClick={(_id, name) => setPrefill(`Tell me about the ${name} stage and what I need to do.`)}
            onCompleteItem={handleCompleteItem}
            onEscalate={() => setShowEscalation(true)}
            onAdvanceStage={handleAdvanceStage}
            onOpenAdmin={() => setShowAdmin(true)}
            isAdmin={isAdmin}
            uploadedFiles={uploadedFiles}
            onUpload={f => void handleUpload(f)}
            isUploading={isUploading}
            username={username}
            userSessions={userSessions}
            activeSessionId={conversationId.current}
            onSelectSession={sid => {
              conversationId.current = sid
              localStorage.setItem('hr_copilot_conversation_id', sid)
              setMessages([])
              localStorage.removeItem('hr_copilot_messages')
            }}
            authUser={authUser}
            userProfile={userProfile}
            onLogout={handleLogoutFull}
          />
        </div>

        {/* Main panel */}
        <div className="flex-1 flex flex-col min-w-0">
          <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-surface-panel">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
                <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-slate-200">HR Onboarding</span>
            </div>
            <div className="flex items-center gap-2">
              {onboardingCase && <button onClick={() => setShowEscalation(true)} className="text-xs text-amber-500">Get Help</button>}
              {messages.length > 0 && <button onClick={clearChat} className="text-xs text-slate-600 hover:text-slate-400">Clear</button>}
              <button onClick={handleLogoutFull} className="text-xs text-slate-600 hover:text-rose-400 transition-colors ml-1">Sign out</button>
            </div>
          </header>

          {username && (
            <div className="lg:hidden flex items-center gap-2 px-4 py-1.5 bg-surface-panel border-b border-white/[0.04]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-[10px] text-slate-600 font-mono">{username}</span>
            </div>
          )}

          <main className="flex-1 overflow-y-auto scrollbar-dark" role="main" aria-live="polite" aria-atomic="false" aria-relevant="additions">
            <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
              {messages.map(msg => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onRetry={msg.isError ? handleRetry : undefined}
                  onFollowUp={q => void sendMessage(q, userId, onboardingCase?.case_id)}
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
              <ChatInput
                onSend={content => void sendMessage(content, userId, onboardingCase?.case_id)}
                isLoading={isLoading}
                prefill={prefill}
                onPrefillConsumed={() => setPrefill('')}
              />
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
