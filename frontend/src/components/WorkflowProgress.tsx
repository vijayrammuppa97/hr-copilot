import React from 'react'
import { OnboardingCase } from '../types'

interface Props {
  case_: OnboardingCase
  onStageClick: (stageId: string, stageName: string) => void
  onCompleteItem: (stageId: string, itemId: string) => void
}


const WorkflowProgress: React.FC<Props> = ({ case_, onStageClick, onCompleteItem }) => {
  const totalItems     = case_.workflow.reduce((s, st) => s + st.total_items, 0)
  const completedItems = case_.workflow.reduce((s, st) => s + st.completed_items, 0)
  const pct            = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

  const currentStageData = case_.workflow.find((s) => s.stage_id === case_.current_stage)

  return (
    <div className="flex flex-col gap-0 w-full">

      {/* Overall progress bar */}
      <div className="px-3 pb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em]">Onboarding Progress</span>
          <span className="text-[10px] font-semibold text-slate-400 tabular-nums">{pct}%</span>
        </div>
        <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-[9px] text-slate-700 mt-1">{completedItems} of {totalItems} tasks complete</p>
      </div>

      {/* Stage list */}
      <nav aria-label="Onboarding stages">
        <ul className="space-y-0.5 px-2 list-none p-0 m-0">
          {case_.workflow.map((stage) => {
            const isCurrent = stage.stage_id === case_.current_stage
            return (
              <li key={stage.stage_id}>
                <button
                  onClick={() => onStageClick(stage.stage_id, stage.name)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all duration-150 text-left group
                    ${isCurrent
                      ? 'bg-indigo-500/[0.1] border border-indigo-500/20 text-slate-200'
                      : 'hover:bg-white/[0.04] border border-transparent text-slate-500 hover:text-slate-300'
                    }`}
                >
                  <span className="text-base leading-none select-none" aria-hidden="true">{stage.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className={`text-xs font-medium truncate ${isCurrent ? 'text-slate-200' : 'text-slate-500 group-hover:text-slate-300'}`}>
                        {stage.name}
                      </span>
                      {stage.status === 'completed' && (
                        <svg className="w-3 h-3 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                      {isCurrent && stage.status !== 'completed' && (
                        <span className="text-[9px] font-medium text-indigo-400 flex-shrink-0">Active</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className="flex-1 h-0.5 bg-white/[0.06] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            stage.status === 'completed' ? 'bg-emerald-400' : 'bg-indigo-400'
                          }`}
                          style={{ width: `${stage.total_items > 0 ? (stage.completed_items / stage.total_items) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-slate-700 tabular-nums flex-shrink-0">
                        {stage.completed_items}/{stage.total_items}
                      </span>
                    </div>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Current stage checklist */}
      {currentStageData && currentStageData.status !== 'completed' && (
        <div className="mt-3 mx-2 px-3 py-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <p className="text-[9px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-2">
            {currentStageData.icon} Checklist
          </p>
          <ul className="space-y-1.5 list-none p-0 m-0">
            {currentStageData.items.map((item) => (
              <li key={item.id} className="flex items-start gap-2">
                <button
                  onClick={() => item.status !== 'completed' && onCompleteItem(currentStageData.stage_id, item.id)}
                  className={`mt-0.5 w-3.5 h-3.5 rounded flex-shrink-0 border transition-all ${
                    item.status === 'completed'
                      ? 'bg-emerald-500 border-emerald-500 cursor-default'
                      : 'border-white/20 hover:border-indigo-400 cursor-pointer'
                  }`}
                  aria-label={item.status === 'completed' ? `${item.label} done` : `Mark ${item.label} as done`}
                  disabled={item.status === 'completed'}
                >
                  {item.status === 'completed' && (
                    <svg className="w-full h-full text-white p-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
                <div className="min-w-0">
                  <p className={`text-[11px] leading-snug ${item.status === 'completed' ? 'line-through text-slate-600' : 'text-slate-400'}`}>
                    {item.label}
                  </p>
                  <p className="text-[9px] text-slate-700 leading-snug mt-0.5">{item.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default WorkflowProgress
