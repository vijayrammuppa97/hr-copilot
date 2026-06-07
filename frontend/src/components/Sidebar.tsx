import React, { useRef, useState } from 'react'
import { OnboardingCase } from '../types'
import WorkflowProgress from './WorkflowProgress'
import SessionHistory from './SessionHistory'

interface UploadedFile { name: string; sections: number }
interface UserSession { session_id: string; started_at: string; updated_at: string; message_count: number; preview: string | null }
interface AuthUser { token: string; email: string; full_name: string; user_id: string; role?: string }
interface UserProfile { tenure_years?: number | null; employment_type?: string | null; department?: string | null; role?: string | null }

interface Props {
  onNewChat: () => void
  case_: OnboardingCase | null
  onStageClick: (stageId: string, stageName: string) => void
  onCompleteItem: (stageId: string, itemId: string) => void
  onEscalate: () => void
  onAdvanceStage: () => void
  onOpenAdmin: () => void
  isAdmin: boolean
  uploadedFiles: UploadedFile[]
  onUpload: (file: File) => void
  isUploading: boolean
  username: string
  userSessions: UserSession[]
  activeSessionId: string
  onSelectSession: (sessionId: string) => void
  authUser: AuthUser | null
  userProfile: UserProfile | null
  onLogout: () => void
}

function getInitials(name: string): string {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const ProfileRow: React.FC<{ icon: string; label: string; value: string; muted?: boolean }> = ({ icon, label, value, muted }) => (
  <div className="flex items-center gap-2">
    <span className="text-[10px] w-4 flex-shrink-0">{icon}</span>
    <span className="text-[9px] text-slate-600 w-16 flex-shrink-0">{label}</span>
    <span className={`text-[10px] truncate flex-1 min-w-0 ${muted ? 'text-slate-700 italic' : 'text-slate-300'}`}>{value}</span>
  </div>
)

const Sidebar: React.FC<Props> = ({
  onNewChat, case_, onStageClick, onCompleteItem, onEscalate,
  onAdvanceStage, onOpenAdmin, isAdmin, uploadedFiles, onUpload, isUploading,
  username, userSessions, activeSessionId, onSelectSession,
  authUser, userProfile, onLogout,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showSessions, setShowSessions] = useState(false)
  const [showProfile, setShowProfile] = useState(false)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
    e.target.value = ''
  }

  const currentStageData = case_?.workflow.find((s) => s.stage_id === case_.current_stage)
  const currentStageComplete = currentStageData?.status === 'completed'
  const isLastStage = case_?.current_stage === 'payroll_setup'
  const allDone = case_?.status === 'completed'

  return (
    <aside
      className="w-[240px] flex-shrink-0 flex flex-col h-screen bg-surface-panel border-r border-white/[0.06] select-none overflow-y-auto scrollbar-dark"
      aria-label="Onboarding sidebar"
    >
      {/* ── Logo ── */}
      <div className="px-4 pt-5 pb-4 flex-shrink-0">
        <div className="flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0 shadow-glow-sm">
              <svg className="w-[14px] h-[14px] text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-slate-100 leading-none tracking-tight">Acme HR</p>
              <p className="text-[10px] text-slate-600 leading-none mt-[3px]">Onboarding Copilot</p>
            </div>
          </div>
          {isAdmin && (
            <button onClick={onOpenAdmin} title="Admin portal" className="w-6 h-6 flex items-center justify-center rounded-md text-slate-600 hover:text-indigo-400 hover:bg-white/[0.05] transition-all">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </button>
          )}
        </div>
        {/* User profile card */}
        {authUser && (
          <div className="mt-3">
            <button
              onClick={() => setShowProfile(v => !v)}
              className="w-full flex items-center gap-2.5 group text-left"
              title="View profile"
            >
              {/* Avatar */}
              <div className="w-7 h-7 rounded-full bg-indigo-600/30 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-bold text-indigo-300">{getInitials(authUser.full_name || authUser.email)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-medium text-slate-300 truncate leading-none">{authUser.full_name || authUser.email}</p>
                <p className="text-[9px] text-slate-600 truncate mt-[2px]">{authUser.email}</p>
              </div>
              <svg className={`w-3 h-3 text-slate-700 flex-shrink-0 transition-transform ${showProfile ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Expanded profile panel */}
            {showProfile && (
              <div className="mt-2.5 rounded-xl bg-white/[0.03] border border-white/[0.07] p-3 space-y-2.5">
                <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em]">My Profile</p>

                {/* Fields */}
                <div className="space-y-1.5">
                  <ProfileRow icon="✉" label="Email" value={authUser.email} />
                  <ProfileRow icon="👤" label="Name" value={authUser.full_name || '—'} />
                  <ProfileRow icon="🏷" label="Username" value={username || '—'} />
                  <ProfileRow
                    icon="📅"
                    label="Tenure"
                    value={userProfile?.tenure_years != null ? `${userProfile.tenure_years} year${userProfile.tenure_years !== 1 ? 's' : ''}` : 'Not set'}
                    muted={userProfile?.tenure_years == null}
                  />
                  <ProfileRow
                    icon="💼"
                    label="Role"
                    value={userProfile?.role || 'Not set'}
                    muted={!userProfile?.role}
                  />
                  <ProfileRow
                    icon="🏢"
                    label="Department"
                    value={userProfile?.department || 'Not set'}
                    muted={!userProfile?.department}
                  />
                  <ProfileRow
                    icon="⏱"
                    label="Type"
                    value={userProfile?.employment_type || 'Not set'}
                    muted={!userProfile?.employment_type}
                  />
                </div>

                <p className="text-[8px] text-slate-700 leading-relaxed">
                  Profile fields auto-update when you mention them in chat (e.g. "I've worked here 3 years").
                </p>

                {/* Logout */}
                <button
                  onClick={onLogout}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] font-medium text-rose-400 hover:text-rose-300 bg-rose-500/[0.06] hover:bg-rose-500/[0.12] border border-rose-500/[0.12] transition-all"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Employee card ── */}
      {case_ && (
        <div className="mx-3 mb-3 px-3 py-2.5 rounded-xl bg-indigo-500/[0.08] border border-indigo-500/[0.15] flex-shrink-0">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-slate-200 truncate">{case_.employee_name}</p>
              <p className="text-[10px] text-slate-500 truncate mt-0.5">{case_.role || case_.employee_email}</p>
            </div>
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
              case_.status === 'completed'  ? 'bg-emerald-400' :
              case_.status === 'escalated'  ? 'bg-amber-400'   : 'bg-indigo-400'
            }`} />
          </div>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-[9px] text-slate-600 font-mono">{case_.case_id}</span>
          </div>
        </div>
      )}

      {/* ── Divider ── */}
      <div className="h-px bg-white/[0.05] mx-3 mb-3 flex-shrink-0" />

      {/* ── Workflow progress ── */}
      {case_ ? (
        <div className="flex-shrink-0">
          <WorkflowProgress
            case_={case_}
            onStageClick={onStageClick}
            onCompleteItem={onCompleteItem}
          />
        </div>
      ) : (
        <div className="px-4 py-3">
          <p className="text-xs text-slate-600">No active onboarding case</p>
        </div>
      )}

      {/* ── Advance stage button ── */}
      {case_ && currentStageComplete && !allDone && (
        <div className="px-3 mt-3 flex-shrink-0">
          <button
            onClick={onAdvanceStage}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-emerald-300 bg-emerald-500/[0.1] hover:bg-emerald-500/20 border border-emerald-500/20 hover:border-emerald-500/30 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
            {isLastStage ? 'Complete Onboarding' : 'Next Stage →'}
          </button>
        </div>
      )}

      {/* Completed banner */}
      {allDone && (
        <div className="mx-3 mt-3 px-3 py-2.5 rounded-xl bg-emerald-500/[0.1] border border-emerald-500/20 flex-shrink-0">
          <p className="text-xs text-emerald-400 font-medium text-center">🎉 Onboarding Complete!</p>
        </div>
      )}

      {/* ── Spacer ── */}
      <div className="flex-1" />

      {/* ── Divider ── */}
      <div className="h-px bg-white/[0.05] mx-3 mt-3 flex-shrink-0" />

      {/* ── Session history ── */}
      <div className="px-3 pb-3 flex-shrink-0">
        <div className="h-px bg-white/[0.05] mb-3" />
        <button
          onClick={() => setShowSessions((v) => !v)}
          className="w-full flex items-center justify-between mb-2 group"
        >
          <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] group-hover:text-slate-400 transition-colors">
            Session History
          </p>
          <svg className={`w-2.5 h-2.5 text-slate-700 transition-transform ${showSessions ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
        {showSessions && (
          <SessionHistory sessions={userSessions} activeSessionId={activeSessionId} onSelectSession={onSelectSession} />
        )}
      </div>

      {/* ── Documents ── */}
      <div className="px-3 pt-3 pb-2 flex-shrink-0">
        <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-2 px-1">Documents</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.csv,.txt,.md,.text"
          className="hidden"
          onChange={handleFileChange}
          aria-hidden="true"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-200 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.11] transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed group"
        >
          {isUploading ? (
            <svg className="w-3.5 h-3.5 text-indigo-400 animate-spin-slow flex-shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          )}
          <span className="truncate">{isUploading ? 'Uploading…' : 'Attach document'}</span>
        </button>
        {uploadedFiles.length > 0 && (
          <ul className="mt-1.5 space-y-1 list-none p-0 m-0">
            {uploadedFiles.map((f) => (
              <li key={f.name} className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-white/[0.03]">
                <svg className="w-3 h-3 text-slate-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="text-[10px] text-slate-500 truncate flex-1 min-w-0">{f.name}</span>
                <span className="text-[9px] text-slate-700 flex-shrink-0 tabular-nums">{f.sections}§</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Escalation + New Chat ── */}
      <div className="px-3 pb-3 flex-shrink-0 space-y-2">
        {case_ && case_.status !== 'escalated' && (
          <button
            onClick={onEscalate}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-amber-500 hover:text-amber-300 bg-amber-500/[0.06] hover:bg-amber-500/[0.12] border border-amber-500/[0.12] hover:border-amber-500/25 transition-all group"
          >
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Get Human Help
          </button>
        )}
        {case_?.status === 'escalated' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/[0.08] border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
            <span className="text-[11px] text-amber-400">Escalated — HR will contact you</span>
          </div>
        )}
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07] transition-all group"
        >
          <svg className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          New Chat
        </button>
      </div>

      {/* ── Model badge ── */}
      <div className="px-3 pb-4 flex-shrink-0">
        <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.05]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
          <span className="text-[10px] text-slate-600 truncate">llama3.2 · Local · No API key</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
