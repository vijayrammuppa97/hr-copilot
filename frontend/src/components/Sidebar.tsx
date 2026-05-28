import React, { useRef } from 'react'

interface UploadedFile {
  name: string
  sections: number
}

interface Props {
  onNewChat: () => void
  onPromptSelect: (query: string) => void
  hasMessages: boolean
  conversationPreview: string
  uploadedFiles: UploadedFile[]
  onUpload: (file: File) => void
  isUploading: boolean
}

const TOPICS = [
  { label: 'Leave & Time Off',  query: 'What is the annual leave entitlement?',       accent: 'text-sky-400',     dot: 'bg-sky-400'     },
  { label: 'Remote Work',       query: 'What is the remote work policy?',              accent: 'text-violet-400',  dot: 'bg-violet-400'  },
  { label: 'Benefits',          query: 'What employee benefits are available?',         accent: 'text-emerald-400', dot: 'bg-emerald-400' },
  { label: 'Onboarding',        query: 'What happens during onboarding?',               accent: 'text-amber-400',   dot: 'bg-amber-400'   },
  { label: 'Escalation',        query: 'How do I escalate a workplace concern?',        accent: 'text-rose-400',    dot: 'bg-rose-400'    },
]

const Sidebar: React.FC<Props> = ({ onNewChat, onPromptSelect, hasMessages, conversationPreview, uploadedFiles, onUpload, isUploading }) => {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
    e.target.value = ''
  }

  return (
    <aside
      className="w-[224px] flex-shrink-0 flex flex-col h-screen bg-surface-panel border-r border-white/[0.06] select-none"
      aria-label="Navigation sidebar"
    >
      {/* ── Logo ── */}
      <div className="px-4 pt-5 pb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0 shadow-glow-sm">
            <svg className="w-[14px] h-[14px] text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-slate-100 leading-none tracking-tight">Acme HR</p>
            <p className="text-[10px] text-slate-600 leading-none mt-[3px]">Knowledge Copilot</p>
          </div>
        </div>
      </div>

      {/* ── New Chat ── */}
      <div className="px-3 pb-4">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07] hover:border-white/[0.12] transition-all duration-150 group"
          aria-label="Start a new conversation"
        >
          <svg className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New conversation
        </button>
      </div>

      {/* ── Divider ── */}
      <div className="h-px bg-white/[0.05] mx-3" />

      {/* ── Recent ── */}
      <div className="px-3 pt-4 pb-3">
        <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-2 px-1">Recent</p>
        {hasMessages ? (
          <div
            className="px-3 py-2.5 rounded-lg bg-indigo-500/[0.1] border border-indigo-500/[0.18] cursor-default"
            role="listitem"
          >
            <p className="text-xs text-slate-300 truncate leading-snug">
              {conversationPreview || 'Current conversation'}
            </p>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" aria-hidden="true" />
              <p className="text-[10px] text-slate-600">Active now</p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-700 px-1 py-1">No conversations yet</p>
        )}
      </div>

      {/* ── Spacer ── */}
      <div className="flex-1" />

      {/* ── Divider ── */}
      <div className="h-px bg-white/[0.05] mx-3" />

      {/* ── Topics ── */}
      <div className="px-3 pt-4 pb-3">
        <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-2 px-1">Topics</p>
        <nav aria-label="Policy topics">
          <ul className="space-y-0.5 list-none p-0 m-0">
            {TOPICS.map((t) => (
              <li key={t.label}>
                <button
                  onClick={() => onPromptSelect(t.query)}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-slate-500 hover:text-slate-200 hover:bg-white/[0.05] transition-all duration-150 text-left group"
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${t.dot} opacity-70 group-hover:opacity-100 flex-shrink-0 transition-opacity`} aria-hidden="true" />
                  <span className={`text-xs transition-colors group-hover:${t.accent.replace('text-', 'text-')}`}>{t.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      {/* ── Documents ── */}
      <div className="px-3 pb-3">
        <div className="h-px bg-white/[0.05] mb-3" />
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
          aria-label="Upload a document to the knowledge base"
        >
          {isUploading ? (
            <svg className="w-3.5 h-3.5 text-indigo-400 animate-spin-slow flex-shrink-0" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          )}
          <span className="truncate">{isUploading ? 'Uploading…' : 'Attach document'}</span>
        </button>

        {uploadedFiles.length > 0 && (
          <ul className="mt-2 space-y-1 list-none p-0 m-0" aria-label="Uploaded documents">
            {uploadedFiles.map((f) => (
              <li key={f.name} className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-white/[0.03]">
                <svg className="w-3 h-3 text-slate-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="text-[10px] text-slate-500 truncate flex-1 min-w-0">{f.name}</span>
                <span className="text-[9px] text-slate-700 flex-shrink-0 tabular-nums">{f.sections}§</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Model badge ── */}
      <div className="px-3 pb-5">
        <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.05]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" aria-hidden="true" />
          <span className="text-[10px] text-slate-600 truncate">llama3.2 · Local · No API key</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
