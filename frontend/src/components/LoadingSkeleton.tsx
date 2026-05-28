import React from 'react'

const LoadingSkeleton: React.FC = () => (
  <div
    className="flex items-start gap-3 message-enter"
    role="status"
    aria-label="HR Copilot is generating a response"
  >
    {/* Avatar */}
    <div className="w-7 h-7 rounded-lg bg-indigo-600/[0.12] border border-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-0.5 animate-pulse-soft">
      <svg className="w-[14px] h-[14px] text-indigo-600/60" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    </div>

    {/* Card skeleton */}
    <div className="flex-1 max-w-[75%]">
      <div className="bg-surface-card border border-white/[0.07] rounded-2xl rounded-tl-[4px] px-4 py-4 shadow-card overflow-hidden relative">
        {/* Shimmer overlay */}
        <div className="absolute inset-0 shimmer" aria-hidden="true" />

        <div className="space-y-2.5 relative">
          <div className="h-2.5 bg-white/[0.07] rounded-full w-full" />
          <div className="h-2.5 bg-white/[0.07] rounded-full w-[92%]" />
          <div className="h-2.5 bg-white/[0.07] rounded-full w-[85%]" />
          <div className="h-2.5 bg-white/[0.06] rounded-full w-[60%]" />
        </div>
      </div>

      {/* Typing indicator */}
      <div className="flex items-center gap-2 mt-2.5 px-0.5">
        <div className="dot-pulse flex items-center gap-1 text-slate-600" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <span className="text-[10px] text-slate-700">Thinking…</span>
      </div>
    </div>

    <span className="sr-only">Loading response…</span>
  </div>
)

export default LoadingSkeleton
