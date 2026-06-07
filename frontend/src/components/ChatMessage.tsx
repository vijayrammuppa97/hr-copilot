import React, { useState, useCallback } from 'react'
import { Message } from '../types'

interface Props {
  message: Message
  onRetry?: () => void
  onFollowUp?: (q: string) => void
}

interface ConfidenceLabel {
  text: string
  classes: string
  dot: string
}

function getConfidenceLabel(confidence: number | undefined, content: string): ConfidenceLabel | null {
  if (confidence === undefined) return null
  const notFound = content.includes('could not find that information') ||
                   content.includes('not in our HR policy')
  if (notFound || confidence === 0) return null
  if (confidence >= 0.6) {
    return { text: 'High confidence', classes: 'text-emerald-400 bg-emerald-500/[0.08] border-emerald-500/20', dot: 'bg-emerald-400' }
  }
  if (confidence >= 0.3) {
    return { text: 'Moderate confidence', classes: 'text-yellow-400 bg-yellow-500/[0.08] border-yellow-500/20', dot: 'bg-yellow-400' }
  }
  return { text: 'Low confidence — verify with HR', classes: 'text-amber-400 bg-amber-500/[0.08] border-amber-500/20', dot: 'bg-amber-400' }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const CopyIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
)

const CheckIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const ChatMessage: React.FC<Props> = ({ message, onRetry, onFollowUp }) => {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const confidenceLabel = !isUser && !message.isError
    ? getConfidenceLabel(message.confidence, message.content)
    : null

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = message.content
      ta.style.cssText = 'position:fixed;opacity:0'
      document.body.appendChild(ta)
      ta.focus(); ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  // ── User message ─────────────────────────────────────────────────────── //
  if (isUser) {
    return (
      <div
        className="flex justify-end message-enter"
        role="article"
        aria-label={`Your message at ${formatTime(message.timestamp)}`}
      >
        <div className="max-w-[72%] flex flex-col items-end">
          <div className="bg-indigo-600 text-white rounded-2xl rounded-br-[4px] px-4 py-3 shadow-card surface-highlight">
            <p className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          <time className="text-[10px] text-slate-700 mt-1.5 px-0.5" dateTime={message.timestamp}>
            {formatTime(message.timestamp)}
          </time>
        </div>
      </div>
    )
  }

  // ── AI error message ─────────────────────────────────────────────────── //
  if (message.isError) {
    return (
      <div
        className="flex items-start gap-3 message-enter"
        role="alert"
        aria-label={`Error at ${formatTime(message.timestamp)}`}
      >
        <div className="w-7 h-7 rounded-lg bg-rose-500/[0.12] border border-rose-500/25 flex items-center justify-center flex-shrink-0 mt-0.5">
          <svg className="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="max-w-[82%]">
          <div className="bg-rose-950/30 border border-rose-500/[0.18] rounded-2xl rounded-tl-[4px] px-4 py-3.5">
            <p className="text-[13px] text-rose-300 leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-300 bg-rose-500/[0.12] hover:bg-rose-500/20 border border-rose-500/25 rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-rose-500/40"
                aria-label="Retry this message"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Try again
              </button>
            )}
          </div>
          <time className="text-[10px] text-slate-700 mt-1.5 px-0.5 block" dateTime={message.timestamp}>
            {formatTime(message.timestamp)}
          </time>
        </div>
      </div>
    )
  }

  // ── AI response card ─────────────────────────────────────────────────── //
  return (
    <div
      className="flex items-start gap-3 message-enter group"
      role="article"
      aria-label={`HR Copilot response at ${formatTime(message.timestamp)}`}
    >
      {/* Avatar */}
      <div className="w-7 h-7 rounded-lg bg-indigo-600/[0.15] border border-indigo-500/25 flex items-center justify-center flex-shrink-0 mt-0.5">
        <svg className="w-[14px] h-[14px] text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 max-w-[85%]">
        {/* Main card */}
        <div className="bg-surface-card border border-white/[0.07] rounded-2xl rounded-tl-[4px] px-4 py-4 shadow-card surface-highlight">
          <p className="text-[13px] text-slate-300 leading-[1.75] whitespace-pre-wrap break-words">{message.content}</p>
        </div>

        {/* Confidence badge */}
        {confidenceLabel && (
          <div className="flex items-center gap-1.5 mt-2.5 px-0.5">
            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium border ${confidenceLabel.classes}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${confidenceLabel.dot}`} />
              {confidenceLabel.text}
            </span>
            {message.sources && message.sources.length > 0 && (
              <span className="text-[10px] text-slate-600 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {message.sources.map(s => s.replace(/^knowledge_base\s*[—–-]\s*/i, '')).join(' · ')}
              </span>
            )}
          </div>
        )}

        {/* Follow-up question chips */}
        {message.followUpQuestions && message.followUpQuestions.length > 0 && onFollowUp && (
          <div className="mt-3 px-0.5">
            <p className="text-[10px] text-slate-600 mb-1.5">You might also ask:</p>
            <div className="flex flex-wrap gap-1.5">
              {message.followUpQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => onFollowUp(q)}
                  className="text-[11px] text-indigo-300 bg-indigo-500/[0.08] hover:bg-indigo-500/[0.15] border border-indigo-500/20 hover:border-indigo-500/40 rounded-lg px-2.5 py-1 transition-all duration-150 text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer row */}
        <div className="flex items-center gap-3 mt-2 px-0.5">
          <time className="text-[10px] text-slate-700" dateTime={message.timestamp}>
            {formatTime(message.timestamp)}
          </time>
          <button
            onClick={() => void handleCopy()}
            className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity text-slate-700 hover:text-slate-400 focus:outline-none"
            aria-label={copied ? 'Copied to clipboard' : 'Copy response'}
            title={copied ? 'Copied!' : 'Copy'}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatMessage
