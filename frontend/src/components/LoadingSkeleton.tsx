import React from 'react'

const LoadingSkeleton: React.FC = () => (
  <div
    className="flex items-start gap-3"
    role="status"
    aria-label="HR Copilot is composing a response"
  >
    {/* Avatar skeleton */}
    <div
      className="w-8 h-8 rounded-full bg-blue-200 animate-pulse flex-shrink-0 mt-0.5"
      aria-hidden="true"
    />

    <div className="flex flex-col gap-2 w-64 max-w-[78%]">
      {/* Bubble skeleton */}
      <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm space-y-2.5">
        <div className="h-3 bg-gray-200 rounded-full animate-pulse w-full" />
        <div className="h-3 bg-gray-200 rounded-full animate-pulse w-5/6" />
        <div className="h-3 bg-gray-200 rounded-full animate-pulse w-3/4" />
        <div className="h-3 bg-gray-200 rounded-full animate-pulse w-4/6" />
      </div>

      {/* Source chip skeletons */}
      <div className="flex gap-1.5 px-0.5">
        <div className="h-5 w-20 bg-blue-100 rounded-full animate-pulse" />
        <div className="h-5 w-24 bg-blue-100 rounded-full animate-pulse" />
      </div>
    </div>

    <span className="sr-only">Loading…</span>
  </div>
)

export default LoadingSkeleton
