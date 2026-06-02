import React, { useState } from 'react'

interface Session {
  session_id: string
  started_at: string
  updated_at: string
  message_count: number
  preview: string | null
}

interface Props {
  sessions: Session[]
  activeSessionId: string
  onSelectSession: (sessionId: string) => void
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(today.getDate() - 1)
    if (d.toDateString() === today.toDateString()) return 'Today'
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() !== today.getFullYear() ? 'numeric' : undefined })
  } catch { return iso.slice(0, 10) }
}

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

function groupByDate(sessions: Session[]): Map<string, Session[]> {
  const groups = new Map<string, Session[]>()
  for (const s of sessions) {
    const label = formatDate(s.updated_at)
    const group = groups.get(label) ?? []
    group.push(s)
    groups.set(label, group)
  }
  return groups
}

const SessionHistory: React.FC<Props> = ({ sessions, activeSessionId, onSelectSession }) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  if (sessions.length === 0) {
    return <p className="text-[10px] text-slate-700 px-1 py-2">No previous sessions</p>
  }

  const groups = groupByDate(sessions)

  return (
    <nav aria-label="Session history" className="space-y-3">
      {Array.from(groups.entries()).map(([label, groupSessions]) => {
        const isCollapsed = collapsed.has(label)
        return (
          <div key={label}>
            {/* Date group header */}
            <button
              onClick={() => setCollapsed((prev) => {
                const next = new Set(prev)
                if (next.has(label)) next.delete(label)
                else next.add(label)
                return next
              })}
              className="w-full flex items-center gap-1.5 mb-1 text-left group"
            >
              <svg
                className={`w-2.5 h-2.5 text-slate-600 transition-transform flex-shrink-0 ${isCollapsed ? '' : 'rotate-90'}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.1em] group-hover:text-slate-400 transition-colors">
                {label}
              </span>
              <span className="text-[9px] text-slate-700 ml-auto">{groupSessions.length}</span>
            </button>

            {/* Session list */}
            {!isCollapsed && (
              <ul className="space-y-0.5 list-none p-0 m-0 pl-3 border-l border-white/[0.06]">
                {groupSessions.map((s) => {
                  const isActive = s.session_id === activeSessionId
                  const preview  = s.preview?.slice(0, 50) ?? 'Session'
                  return (
                    <li key={s.session_id}>
                      <button
                        onClick={() => onSelectSession(s.session_id)}
                        className={`w-full text-left px-2 py-1.5 rounded-md transition-all text-[11px] group ${
                          isActive
                            ? 'bg-indigo-500/[0.12] text-slate-200'
                            : 'text-slate-600 hover:text-slate-300 hover:bg-white/[0.04]'
                        }`}
                      >
                        <p className="truncate leading-snug">{preview}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[9px] text-slate-700">{formatTime(s.updated_at)}</span>
                          <span className="text-[9px] text-slate-700">·</span>
                          <span className="text-[9px] text-slate-700">{s.message_count} msg</span>
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        )
      })}
    </nav>
  )
}

export default SessionHistory
