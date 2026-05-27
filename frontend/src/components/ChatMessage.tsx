import React, { useState, useCallback } from 'react'
import { Message, FeedbackValue } from '../types'

interface Props {
  message: Message
  onFeedback?: (messageId: string, value: FeedbackValue) => void
  onRetry?: () => void
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

// ── Icon components ──────────────────────────────────────────────────────── //

const UserIcon: React.FC = () => (
  <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
)

const BotIcon: React.FC = () => (
  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
)

const CopyIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
)

const CheckIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const ThumbUpIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
  </svg>
)

const ThumbDownIcon: React.FC = () => (
  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
  </svg>
)

function confidenceColor(c: number): string {
  if (c >= 0.75) return 'bg-green-500'
  if (c >= 0.45) return 'bg-yellow-500'
  return 'bg-red-400'
}

// ── Component ────────────────────────────────────────────────────────────── //

const ChatMessage: React.FC<Props> = ({ message, onFeedback, onRetry }) => {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const currentFeedback = message.feedback ?? null

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = message.content
      ta.style.cssText = 'position:fixed;opacity:0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  const handleFeedback = useCallback(
    (value: FeedbackValue) => {
      if (currentFeedback !== null) return // already rated
      onFeedback?.(message.id, value)
    },
    [currentFeedback, message.id, onFeedback]
  )

  return (
    <article
      className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
      aria-label={`${isUser ? 'Your' : 'HR Copilot'} message at ${formatTime(message.timestamp)}`}
    >
      {/* ── Avatar ── */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
          isUser ? 'bg-gray-200' : message.isError ? 'bg-red-500' : 'bg-blue-600'
        }`}
        aria-hidden="true"
      >
        {isUser ? <UserIcon /> : <BotIcon />}
      </div>

      {/* ── Bubble + metadata ── */}
      <div className={`max-w-[78%] flex flex-col ${isUser ? 'items-end' : 'items-start'} group`}>

        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-2.5 shadow-sm ${
            isUser
              ? 'bg-blue-600 text-white rounded-tr-sm'
              : message.isError
              ? 'bg-red-50 border border-red-200 text-red-800 rounded-tl-sm'
              : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm'
          }`}
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>

          {/* Retry button inside error bubble */}
          {message.isError && onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-red-400"
              aria-label="Retry this message"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Try again
            </button>
          )}
        </div>

        {/* Sources / citations */}
        {!isUser && !message.isError && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5 px-0.5" role="list" aria-label="Policy sources cited">
            <span className="text-xs text-gray-400 self-center mr-0.5">Sources:</span>
            {message.sources.map((src, i) => (
              <span
                key={i}
                role="listitem"
                className="inline-block px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded-full border border-blue-200"
              >
                {src}
              </span>
            ))}
          </div>
        )}

        {/* Confidence meter */}
        {!isUser && !message.isError && message.confidence !== undefined && (
          <div
            className="flex items-center gap-2 mt-1 px-0.5"
            aria-label={`Answer confidence: ${Math.round(message.confidence * 100)}%`}
          >
            <div className="w-16 h-1 bg-gray-200 rounded-full overflow-hidden" role="progressbar" aria-valuenow={Math.round(message.confidence * 100)} aria-valuemin={0} aria-valuemax={100}>
              <div
                className={`h-full rounded-full transition-all ${confidenceColor(message.confidence)}`}
                style={{ width: `${message.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">{Math.round(message.confidence * 100)}% confident</span>
          </div>
        )}

        {/* Timestamp + copy + feedback */}
        <div className={`flex items-center gap-2 mt-1.5 px-0.5 ${isUser ? 'flex-row-reverse' : ''}`}>
          <time className="text-xs text-gray-400" dateTime={message.timestamp}>
            {formatTime(message.timestamp)}
          </time>

          {/* Copy button — assistant messages only */}
          {!isUser && (
            <button
              onClick={() => void handleCopy()}
              className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity text-gray-400 hover:text-gray-600 focus:outline-none"
              aria-label={copied ? 'Message copied to clipboard' : 'Copy message to clipboard'}
              title={copied ? 'Copied!' : 'Copy'}
            >
              {copied ? <CheckIcon /> : <CopyIcon />}
            </button>
          )}

          {/* Feedback buttons — non-error assistant messages only */}
          {!isUser && !message.isError && onFeedback && (
            <div
              className={`flex items-center gap-1 transition-opacity ${
                currentFeedback !== null ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
              }`}
              role="group"
              aria-label="Was this response helpful?"
            >
              <span className="text-xs text-gray-400 mr-0.5">Helpful?</span>
              <button
                onClick={() => handleFeedback('helpful')}
                disabled={currentFeedback !== null}
                className={`p-1 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-green-400 disabled:cursor-default ${
                  currentFeedback === 'helpful'
                    ? 'text-green-600 bg-green-100'
                    : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                }`}
                aria-label="Mark as helpful"
                aria-pressed={currentFeedback === 'helpful'}
              >
                <ThumbUpIcon />
              </button>
              <button
                onClick={() => handleFeedback('not_helpful')}
                disabled={currentFeedback !== null}
                className={`p-1 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-red-400 disabled:cursor-default ${
                  currentFeedback === 'not_helpful'
                    ? 'text-red-600 bg-red-100'
                    : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                }`}
                aria-label="Mark as not helpful"
                aria-pressed={currentFeedback === 'not_helpful'}
              >
                <ThumbDownIcon />
              </button>

              {/* Confirmation message after rating */}
              {currentFeedback !== null && (
                <span className="text-xs text-gray-400 ml-1">
                  {currentFeedback === 'helpful' ? 'Thanks!' : 'Sorry about that.'}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

export default ChatMessage
