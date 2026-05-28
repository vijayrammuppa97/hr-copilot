import React from 'react'
import { Message, FeedbackValue } from '../types'

interface Props {
  message: Message | null
  onFeedback: (messageId: string, value: FeedbackValue) => void
}

function confidenceMeta(c: number): { label: string; tier: string; barColor: string; desc: string } {
  if (c >= 0.85) return { label: 'High',    tier: 'text-emerald-400', barColor: 'bg-emerald-500', desc: 'Strong KB match. Answer is well-grounded in policy.' }
  if (c >= 0.70) return { label: 'Good',    tier: 'text-sky-400',     barColor: 'bg-sky-500',     desc: 'Good coverage. Response is generally reliable.' }
  if (c >= 0.55) return { label: 'Partial', tier: 'text-amber-400',   barColor: 'bg-amber-500',   desc: 'Partial match. Recommend verifying with HR.' }
  return               { label: 'Low',     tier: 'text-rose-400',    barColor: 'bg-rose-500',    desc: 'Weak match. Contact HR directly for accuracy.' }
}

const EmptyState: React.FC = () => (
  <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
    <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.07] flex items-center justify-center mb-4">
      <svg className="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    </div>
    <p className="text-[11px] text-slate-600 leading-relaxed max-w-[160px]">
      Ask a question to see policy sources and confidence here.
    </p>
  </div>
)

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-3">{children}</p>
)

const InsightPanel: React.FC<Props> = ({ message, onFeedback }) => {
  return (
    <aside
      className="w-[256px] flex-shrink-0 flex flex-col h-screen bg-surface-panel border-l border-white/[0.06] overflow-y-auto scrollbar-dark"
      aria-label="Response insights"
    >
      {/* ── Header ── */}
      <div className="px-4 pt-5 pb-4 border-b border-white/[0.06]">
        <p className="text-[11px] font-semibold text-slate-400 tracking-tight">Response Insights</p>
        <p className="text-[10px] text-slate-700 mt-0.5">Retrieved context · Confidence · Sources</p>
      </div>

      {!message ? (
        <EmptyState />
      ) : (
        <div className="animate-fade-in">

          {/* ── Confidence ── */}
          <div className="px-4 py-4 border-b border-white/[0.06]">
            <SectionLabel>Retrieval Confidence</SectionLabel>
            {(() => {
              const c = message.confidence ?? 0
              const meta = confidenceMeta(c)
              return (
                <>
                  <div className="flex items-center justify-between mb-2.5">
                    <span className={`text-sm font-semibold ${meta.tier}`}>{meta.label}</span>
                    <span className="text-sm font-mono text-slate-500 tabular-nums">{Math.round(c * 100)}%</span>
                  </div>
                  <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden mb-2">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${meta.barColor}`}
                      style={{ width: `${c * 100}%` }}
                      role="progressbar"
                      aria-valuenow={Math.round(c * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    />
                  </div>
                  <p className="text-[10px] text-slate-600 leading-relaxed">{meta.desc}</p>
                </>
              )
            })()}
          </div>

          {/* ── Policy Sources ── */}
          {message.sources && message.sources.length > 0 && (
            <div className="px-4 py-4 border-b border-white/[0.06]">
              <SectionLabel>Policy Sources</SectionLabel>
              <ul className="space-y-1.5 list-none p-0 m-0">
                {message.sources.map((src, i) => (
                  <li key={i}>
                    <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.07] hover:border-indigo-500/25 hover:bg-indigo-500/[0.05] transition-all duration-150 cursor-default group">
                      <div className="w-4 h-4 rounded bg-indigo-500/[0.15] flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-[8px] font-bold text-indigo-400 tabular-nums">{i + 1}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-snug group-hover:text-slate-300 transition-colors">{src}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── AI Grounding ── */}
          <div className="px-4 py-4 border-b border-white/[0.06]">
            <SectionLabel>AI Grounding</SectionLabel>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Responses use only the Acme HR knowledge base. The model does not use external data or personal employee information.
            </p>
          </div>

          {/* ── Feedback ── */}
          {!message.isError && (
            <div className="px-4 py-4 border-b border-white/[0.06]">
              <SectionLabel>Response Quality</SectionLabel>
              {message.feedback ? (
                <div className="flex items-center gap-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${message.feedback === 'helpful' ? 'bg-emerald-400' : 'bg-rose-400'}`}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-slate-500">
                    {message.feedback === 'helpful' ? 'Marked as helpful — thanks!' : 'Marked unhelpful — we\'ll improve.'}
                  </span>
                </div>
              ) : (
                <div className="flex gap-2" role="group" aria-label="Was this response helpful?">
                  <button
                    onClick={() => onFeedback(message.id, 'helpful')}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium text-slate-500 bg-white/[0.04] hover:bg-emerald-500/[0.12] hover:text-emerald-400 border border-white/[0.07] hover:border-emerald-500/25 transition-all duration-150"
                    aria-label="Mark as helpful"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                    </svg>
                    Helpful
                  </button>
                  <button
                    onClick={() => onFeedback(message.id, 'not_helpful')}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium text-slate-500 bg-white/[0.04] hover:bg-rose-500/[0.12] hover:text-rose-400 border border-white/[0.07] hover:border-rose-500/25 transition-all duration-150"
                    aria-label="Mark as not helpful"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                    </svg>
                    Not helpful
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Escalate to HR ── */}
          <div className="px-4 py-4">
            <SectionLabel>Need Human Support?</SectionLabel>
            <div className="rounded-xl bg-white/[0.03] border border-white/[0.07] p-3.5">
              <p className="text-[11px] text-slate-600 leading-relaxed mb-3">
                Sensitive situations, PIP, grievances, or decisions requiring HR judgement.
              </p>
              <a
                href="mailto:hr@acme.com"
                className="flex items-center justify-center gap-1.5 w-full py-2 rounded-lg bg-indigo-600/75 hover:bg-indigo-600 text-xs font-medium text-white transition-all duration-150 hover:shadow-glow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Escalate to HR
              </a>
            </div>
          </div>

        </div>
      )}
    </aside>
  )
}

export default InsightPanel
