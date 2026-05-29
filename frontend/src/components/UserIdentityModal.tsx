import React, { useState, FormEvent } from 'react'
import { CreateCaseRequest, OnboardingCase } from '../types'

interface Props {
  apiBase: string
  onCaseCreated: (case_: OnboardingCase) => void
}

const FIELDS: { key: keyof CreateCaseRequest; label: string; placeholder: string; required: boolean; type?: string }[] = [
  { key: 'employee_name',  label: 'Full Name',        placeholder: 'e.g. Priya Sharma',             required: true  },
  { key: 'employee_email', label: 'Work Email',        placeholder: 'e.g. priya@acme.com',           required: true, type: 'email' },
  { key: 'employee_id',    label: 'Employee ID',       placeholder: 'e.g. EMP-0042 (if assigned)',   required: false },
  { key: 'role',           label: 'Designation / Role',placeholder: 'e.g. Software Engineer',        required: false },
  { key: 'department',     label: 'Department',        placeholder: 'e.g. Engineering',              required: false },
  { key: 'manager_name',   label: 'Manager Name',      placeholder: 'e.g. Rahul Menon',              required: false },
  { key: 'start_date',     label: 'Joining Date',      placeholder: 'e.g. 2026-06-01',               required: false, type: 'date' },
]

const UserIdentityModal: React.FC<Props> = ({ apiBase, onCaseCreated }) => {
  const [form, setForm] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/api/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_name:  form.employee_name?.trim() || '',
          employee_email: form.employee_email?.trim() || '',
          employee_id:    form.employee_id?.trim() || '',
          role:           form.role?.trim() || '',
          department:     form.department?.trim() || '',
          manager_name:   form.manager_name?.trim() || '',
          start_date:     form.start_date?.trim() || '',
        } satisfies CreateCaseRequest),
      })
      if (!res.ok) {
        const j = (await res.json()) as { detail?: string }
        throw new Error(j.detail ?? `Server error ${res.status}`)
      }
      const case_ = (await res.json()) as OnboardingCase
      onCaseCreated(case_)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create case. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-surface-panel border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="px-8 pt-8 pb-6 border-b border-white/[0.06]">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
              <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100 tracking-tight">Welcome to Onboarding</h2>
              <p className="text-xs text-slate-500 mt-0.5">Let's set up your onboarding profile to get started</p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4 max-h-[60vh] overflow-y-auto scrollbar-dark">
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label className="block text-[11px] font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                {f.label} {f.required && <span className="text-rose-400">*</span>}
              </label>
              <input
                type={f.type ?? 'text'}
                placeholder={f.placeholder}
                required={f.required}
                value={form[f.key] ?? ''}
                onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))}
                className="w-full px-3.5 py-2.5 rounded-lg bg-surface-card border border-white/[0.08] focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30 text-[13px] text-slate-200 placeholder-slate-600 outline-none transition-all"
              />
            </div>
          ))}

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-rose-950/40 border border-rose-500/20">
              <svg className="w-3.5 h-3.5 text-rose-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <p className="text-xs text-rose-300">{error}</p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="px-8 py-5 border-t border-white/[0.06] flex items-center justify-between">
          <p className="text-[10px] text-slate-600 max-w-[240px] leading-relaxed">
            Your information is used only to personalise your onboarding experience.
          </p>
          <button
            type="submit"
            form=""
            onClick={handleSubmit as unknown as React.MouseEventHandler}
            disabled={loading || !form.employee_name?.trim() || !form.employee_email?.trim()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-white/[0.06] disabled:text-slate-600 disabled:cursor-not-allowed text-white text-sm font-medium transition-all shadow-glow-sm"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin-slow" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Creating…
              </>
            ) : (
              <>
                Start Onboarding
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  )
}

export default UserIdentityModal
