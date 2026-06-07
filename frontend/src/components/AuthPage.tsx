import React, { useState, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL ?? ''
const ALLOWED_DOMAIN = 'acme.com'

interface AuthUser {
  token:     string
  email:     string
  full_name: string
  user_id:   string
  role?:     string
}

interface Props {
  onAuth: (user: AuthUser) => void
}

type Mode = 'login' | 'signup'

const EyeIcon: React.FC<{ visible: boolean }> = ({ visible }) => (
  visible ? (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  ) : (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  )
)

const AuthPage: React.FC<Props> = ({ onAuth }) => {
  const [mode, setMode]             = useState<Mode>('login')
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [fullName, setFullName]     = useState('')
  const [showPwd, setShowPwd]       = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [loading, setLoading]       = useState(false)
  const [success, setSuccess]       = useState<string | null>(null)

  const emailValid = email.endsWith(`@${ALLOWED_DOMAIN}`)

  const resetForm = useCallback((nextMode: Mode) => {
    setMode(nextMode)
    setError(null)
    setSuccess(null)
    setPassword('')
    setConfirmPwd('')
  }, [])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Client-side validation
    if (!emailValid) {
      setError(`Only @${ALLOWED_DOMAIN} email addresses are allowed.`)
      return
    }
    if (mode === 'signup') {
      if (!fullName.trim()) { setError('Full name is required.'); return }
      if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
      if (password !== confirmPwd) { setError('Passwords do not match.'); return }
    }

    setLoading(true)
    try {
      const endpoint = mode === 'signup' ? '/api/auth/signup' : '/api/auth/login'
      const body = mode === 'signup'
        ? { email, password, full_name: fullName.trim() }
        : { email, password }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await res.json() as { token?: string; email?: string; full_name?: string; detail?: string }

      if (!res.ok) {
        setError(data.detail ?? 'Something went wrong. Please try again.')
        return
      }

      if (data.token && data.email) {
        onAuth({ token: data.token, email: data.email, full_name: data.full_name ?? '' })
      }
    } catch {
      setError('Cannot connect to the server. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [mode, email, password, confirmPwd, fullName, emailValid, onAuth])

  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center px-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-indigo-600/[0.04] rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-600/[0.03] rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo + header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/[0.15] border border-indigo-500/25 mb-4">
            <svg className="w-7 h-7 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-slate-200 tracking-tight">HR Knowledge Copilot</h1>
          <p className="text-xs text-slate-500 mt-1">Acme Corp — People & Culture</p>
        </div>

        {/* Card */}
        <div className="bg-surface-card border border-white/[0.07] rounded-2xl shadow-card p-8">
          {/* Mode toggle buttons */}
          <div className="flex rounded-xl bg-surface-base border border-white/[0.06] p-1 mb-7">
            <button
              type="button"
              onClick={() => resetForm('login')}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all duration-150 ${
                mode === 'login'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => resetForm('signup')}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all duration-150 ${
                mode === 'signup'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
            {/* Full name — signup only */}
            {mode === 'signup' && (
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                  Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  placeholder="Jane Smith"
                  autoComplete="name"
                  required
                  className="w-full bg-surface-base border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3.5 py-2.5 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                />
              </div>
            )}

            {/* Email */}
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                Acme Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value.trim())}
                  placeholder={`you@${ALLOWED_DOMAIN}`}
                  autoComplete="email"
                  required
                  className={`w-full bg-surface-base border text-slate-200 text-sm rounded-lg px-3.5 py-2.5 placeholder-slate-600 focus:outline-none focus:ring-2 transition-all pr-10 ${
                    email && !emailValid
                      ? 'border-rose-500/50 focus:ring-rose-500/30'
                      : 'border-white/[0.08] focus:ring-indigo-500/50 focus:border-indigo-500/50'
                  }`}
                />
                {email && (
                  <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-mono ${emailValid ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {emailValid ? '✓' : `@${ALLOWED_DOMAIN} only`}
                  </span>
                )}
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={mode === 'signup' ? 'Min. 8 characters' : 'Enter your password'}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  required
                  className="w-full bg-surface-base border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3.5 py-2.5 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400 transition-colors"
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                >
                  <EyeIcon visible={showPwd} />
                </button>
              </div>
            </div>

            {/* Confirm password — signup only */}
            {mode === 'signup' && (
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                  Confirm Password
                </label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPwd}
                  onChange={e => setConfirmPwd(e.target.value)}
                  placeholder="Re-enter your password"
                  autoComplete="new-password"
                  required
                  className={`w-full bg-surface-base border text-slate-200 text-sm rounded-lg px-3.5 py-2.5 placeholder-slate-600 focus:outline-none focus:ring-2 transition-all ${
                    confirmPwd && confirmPwd !== password
                      ? 'border-rose-500/50 focus:ring-rose-500/30'
                      : 'border-white/[0.08] focus:ring-indigo-500/50 focus:border-indigo-500/50'
                  }`}
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 bg-rose-950/40 border border-rose-500/20 rounded-lg px-3.5 py-2.5" role="alert">
                <svg className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                <p className="text-xs text-rose-300">{error}</p>
              </div>
            )}

            {/* Success */}
            {success && (
              <div className="flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/20 rounded-lg px-3.5 py-2.5">
                <span className="text-xs text-emerald-300">{success}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2.5 rounded-lg transition-all duration-150 flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {mode === 'signup' ? 'Creating account…' : 'Signing in…'}
                </>
              ) : (
                mode === 'signup' ? 'Create Account' : 'Sign In'
              )}
            </button>
          </form>

          {/* Footer note */}
          <p className="text-[10px] text-slate-700 text-center mt-5">
            Access restricted to <span className="text-slate-500">@{ALLOWED_DOMAIN}</span> email addresses only.
          </p>
        </div>

        <p className="text-[10px] text-slate-700 text-center mt-4">
          HR Knowledge Copilot v5.0 · Acme Corp Internal Use Only
        </p>
      </div>
    </div>
  )
}

export default AuthPage
