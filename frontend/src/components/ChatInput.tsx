import React, { useState, useRef, useCallback, useEffect, KeyboardEvent, ChangeEvent } from 'react'

interface Props {
  onSend: (message: string) => void
  isLoading: boolean
  prefill?: string
  onPrefillConsumed?: () => void
}

const MAX_CHARS = 2000

const ChatInput: React.FC<Props> = ({ onSend, isLoading, prefill, onPrefillConsumed }) => {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!prefill) return
    setValue(prefill)
    textareaRef.current?.focus()
    onPrefillConsumed?.()
  }, [prefill, onPrefillConsumed])

  const submit = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, isLoading, onSend])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        submit()
      }
    },
    [submit]
  )

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value
    if (next.length > MAX_CHARS) return
    setValue(next)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 136)}px`
  }

  const charsLeft = MAX_CHARS - value.length
  const canSend = value.trim().length > 0 && !isLoading

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); submit() }}
      aria-label="Send a message"
    >
      <div
        className={`flex items-end gap-3 rounded-2xl px-4 py-3 border transition-all duration-200 ${
          focused
            ? 'bg-surface-card border-indigo-500/40 ring-glow'
            : 'bg-surface-card border-white/[0.08] hover:border-white/[0.13]'
        } ${isLoading ? 'opacity-70' : ''}`}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Ask about leave, benefits, remote work, onboarding…"
          rows={1}
          disabled={isLoading}
          maxLength={MAX_CHARS}
          aria-label="Message input"
          aria-multiline="true"
          aria-describedby="input-hint"
          className="flex-1 bg-transparent resize-none text-[13px] text-slate-200 placeholder-slate-600 focus:outline-none disabled:opacity-50 leading-relaxed max-h-[136px] py-0.5"
        />

        <button
          type="submit"
          disabled={!canSend}
          aria-label={isLoading ? 'Sending…' : 'Send message'}
          className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 mb-0.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:ring-offset-1 focus:ring-offset-surface-card ${
            canSend
              ? 'bg-indigo-600 hover:bg-indigo-500 shadow-glow-sm cursor-pointer'
              : 'bg-white/[0.06] cursor-not-allowed'
          }`}
        >
          {isLoading ? (
            <svg className="w-4 h-4 text-slate-400 animate-spin-slow" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg
              className={`w-4 h-4 transition-colors ${canSend ? 'text-white' : 'text-slate-600'}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </div>

      <div id="input-hint" className="flex items-center justify-between mt-1.5 px-1">
        <span className="text-[10px] text-slate-700">↵ Send · Shift+↵ New line</span>
        {charsLeft < 300 && (
          <span
            className={`text-[10px] tabular-nums ${charsLeft < 100 ? 'text-rose-500' : 'text-amber-600'}`}
            aria-live="polite"
          >
            {charsLeft} left
          </span>
        )}
      </div>
    </form>
  )
}

export default ChatInput
