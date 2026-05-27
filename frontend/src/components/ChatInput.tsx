import React, { useState, useRef, useCallback, KeyboardEvent, ChangeEvent } from 'react'

interface Props {
  onSend: (message: string) => void
  isLoading: boolean
}

const MAX_CHARS = 2000

const ChatInput: React.FC<Props> = ({ onSend, isLoading }) => {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    // Reset textarea height
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
    // Auto-expand up to 5 rows
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 130)}px`
  }

  const charsLeft = MAX_CHARS - value.length
  const canSend = value.trim().length > 0 && !isLoading

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      aria-label="Send a message"
    >
      <div
        className={`flex items-end gap-2 bg-gray-50 border rounded-2xl px-3 py-2 transition-colors ${
          isLoading ? 'border-gray-200' : 'border-gray-300 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-400'
        }`}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask about HR policies, leave, benefits…"
          rows={1}
          disabled={isLoading}
          maxLength={MAX_CHARS}
          aria-label="Message input"
          aria-multiline="true"
          aria-describedby="char-count"
          className="flex-1 bg-transparent resize-none text-sm text-gray-800 placeholder-gray-400 focus:outline-none disabled:opacity-50 py-1 max-h-32 leading-relaxed"
        />

        <button
          type="submit"
          disabled={!canSend}
          aria-label={isLoading ? 'Sending…' : 'Send message'}
          className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-colors mb-0.5 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-1 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300"
        >
          {isLoading ? (
            <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </div>

      <div className="flex justify-between mt-1 px-1">
        <span className="text-xs text-gray-400">Shift+Enter for new line</span>
        <span
          id="char-count"
          className={`text-xs ${charsLeft < 200 ? 'text-amber-500' : 'text-gray-400'}`}
          aria-live="polite"
          aria-label={`${charsLeft} characters remaining`}
        >
          {charsLeft < 200 ? `${charsLeft} left` : ''}
        </span>
      </div>
    </form>
  )
}

export default ChatInput
