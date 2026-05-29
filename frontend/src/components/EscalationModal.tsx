import React, { useState, FormEvent } from 'react'

interface Props {
  caseId: string
  apiBase: string
  onClose: () => void
  onEscalated: (message: string) => void
}

const QUICK_REASONS = [
  'I have a question that the assistant cannot answer',
  'I need help with my offer letter terms',
  'There is an issue with my access or equipment',
  'I have a concern I prefer to discuss with a person',
  'My background verification has a discrepancy',
]

const EscalationModal: React.FC<Props> = ({ caseId, apiBase, onClose, onEscalated }) => {
  const [reason, setReason]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!reason.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiBase}/api/cases/${caseId}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason.trim(), escalated_by: 'employee' }),
      })
      if (!res.ok) {
        const j = (await res.json()) as { detail?: string }
        throw new Error(j.detail ?? `Server error ${res.status}`)
      }
      const data = (await res.json()) as { message: string }
      onEscalated(data.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to escalate. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-surface-panel border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="px-6 pt-6 pb-5 border-b border-white/[0.06] flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/25 flex items-center justify-center flex-shrink-0">
              <svg className="w-4.5 h-4.5 text-amber-400 w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h2 className="text-[15px] font-semibold text-slate-100">Get Human Help</h2>
              <p className="text-[11px] text-slate-500 mt-0.5">An HR rep will reach out within 1 business day</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-600 hover:text-slate-300 transition-colors mt-0.5" aria-label="Close">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          {/* Quick reasons */}
          <div>
            <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-[0.1em] mb-2">Quick select</p>
            <div className="space-y-1.5">
              {QUICK_REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className={`w-full text-left text-[12px] px-3 py-2 rounded-lg border transition-all ${
                    reason === r
                      ? 'bg-amber-500/[0.1] border-amber-500/30 text-amber-300'
                      : 'border-white/[0.07] text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Custom reason */}
          <div>
            <label className="block text-[10px] font-semibold text-slate-600 uppercase tracking-[0.1em] mb-1.5">
              Or describe your issue
            </label>
            <textarea
              rows={3}
              placeholder="Explain what you need help with…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg bg-surface-card border border-white/[0.08] focus:border-amber-500/40 focus:ring-1 focus:ring-amber-500/20 text-[13px] text-slate-200 placeholder-slate-600 outline-none resize-none transition-all"
            />
          </div>

          {error && (
            <p className="text-xs text-rose-400">{error}</p>
          )}
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/[0.06] flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => void submit()}
            disabled={loading || !reason.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:bg-white/[0.06] disabled:text-slate-600 disabled:cursor-not-allowed text-white text-xs font-medium transition-all"
          >
            {loading ? 'Escalating…' : 'Escalate to HR'}
          </button>
        </div>

      </div>
    </div>
  )
}

export default EscalationModal
