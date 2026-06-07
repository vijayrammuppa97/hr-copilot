import React, { useEffect, useState, useCallback } from 'react'

interface Stats {
  total_messages: number
  total_users: number
  total_cases: number
  avg_confidence: number
  messages_today: number
  open_escalations: number
}

interface TopQuery { query: string; frequency: number; last_seen: string }
interface ConfBucket { bucket: number; count: number }
interface DailyCount { date: string; count: number }
interface EvalRow { conversation_id: string; query: string; recall_at_k: number; faithfulness: number; relevance_score: number; timestamp: string }
interface EvalSummary { averages: Record<string, number>; recent: EvalRow[] }

const API_BASE = import.meta.env.VITE_API_URL ?? ''

function pct(v: number) { return `${Math.round(v * 100)}%` }

// Simple bar using a div
const Bar: React.FC<{ value: number; max: number; color?: string }> = ({ value, max, color = 'bg-indigo-500' }) => (
  <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden flex-1">
    <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${max > 0 ? (value / max) * 100 : 0}%` }} />
  </div>
)

const StatCard: React.FC<{ label: string; value: string | number; sub?: string; accent?: string }> = ({ label, value, sub, accent = 'text-slate-100' }) => (
  <div className="px-4 py-4 rounded-xl bg-surface-card border border-white/[0.07]">
    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.1em] mb-1">{label}</p>
    <p className={`text-2xl font-bold ${accent} leading-none`}>{value}</p>
    {sub && <p className="text-[10px] text-slate-600 mt-1">{sub}</p>}
  </div>
)

const AdminDashboard: React.FC<{ onClose: () => void; token: string }> = ({ onClose, token }) => {
  const [stats,    setStats]    = useState<Stats | null>(null)
  const [topQ,     setTopQ]     = useState<TopQuery[]>([])
  const [confDist, setConfDist] = useState<ConfBucket[]>([])
  const [daily,    setDaily]    = useState<DailyCount[]>([])
  const [evalData, setEvalData] = useState<EvalSummary | null>(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
      const [s, q, c, d, e] = await Promise.all([
        fetch(`${API_BASE}/api/admin/stats`,                    { headers: h }).then(r => r.json()),
        fetch(`${API_BASE}/api/admin/top-interactions?limit=20`,{ headers: h }).then(r => r.json()),
        fetch(`${API_BASE}/api/admin/confidence-distribution`,  { headers: h }).then(r => r.json()),
        fetch(`${API_BASE}/api/admin/messages-over-time?days=14`,{ headers: h }).then(r => r.json()),
        fetch(`${API_BASE}/api/admin/evaluation`,               { headers: h }).then(r => r.json()),
      ])
      setStats(s); setTopQ(q); setConfDist(c); setDaily(d); setEvalData(e)
    } catch {
      setError('Failed to load admin data. Check that the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const maxFreq = Math.max(...topQ.map(q => q.frequency), 1)
  const maxDay  = Math.max(...daily.map(d => d.count), 1)
  const maxConf = Math.max(...confDist.map(c => c.count), 1)

  return (
    <div className="fixed inset-0 z-50 bg-surface-base overflow-y-auto scrollbar-dark">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between px-8 py-4 bg-surface-panel border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-[15px] font-semibold text-slate-100">Observability Portal</h1>
            <p className="text-[10px] text-slate-600">Admin view — HR Copilot</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => void load()} className="text-xs text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button onClick={onClose} className="text-slate-600 hover:text-slate-300 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-8 py-8 space-y-8">
        {loading && <p className="text-sm text-slate-500 text-center py-20">Loading…</p>}
        {error   && <p className="text-sm text-rose-400 text-center py-20">{error}</p>}

        {!loading && !error && stats && (
          <>
            {/* Stat cards */}
            <section>
              <h2 className="text-[10px] font-semibold text-slate-600 uppercase tracking-[0.12em] mb-3">Overview</h2>
              <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
                <StatCard label="Total Messages"    value={stats.total_messages}                   accent="text-indigo-300" />
                <StatCard label="Today"             value={stats.messages_today}                   accent="text-sky-300" />
                <StatCard label="Users"             value={stats.total_users}                      accent="text-violet-300" />
                <StatCard label="Cases"             value={stats.total_cases}                      accent="text-emerald-300" />
                <StatCard label="Avg Confidence"    value={pct(stats.avg_confidence)}             accent="text-amber-300" />
                <StatCard label="Open Escalations"  value={stats.open_escalations}                accent={stats.open_escalations > 0 ? 'text-rose-400' : 'text-slate-400'} />
              </div>
            </section>

            {/* Chart: Daily messages */}
            <section className="grid grid-cols-2 gap-6">
              <div className="p-5 rounded-xl bg-surface-card border border-white/[0.07]">
                <h2 className="text-[11px] font-semibold text-slate-400 mb-4">Messages — Last 14 Days</h2>
                <div className="flex items-end gap-1 h-24">
                  {daily.map((d) => (
                    <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
                      <div className="w-full bg-indigo-500/70 rounded-t hover:bg-indigo-400 transition-colors"
                           style={{ height: `${maxDay > 0 ? (d.count / maxDay) * 88 : 0}px`, minHeight: d.count > 0 ? '3px' : '0' }}
                           title={`${d.date}: ${d.count}`}
                      />
                    </div>
                  ))}
                  {daily.length === 0 && <p className="text-xs text-slate-700 m-auto">No data yet</p>}
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[9px] text-slate-700">{daily[0]?.date?.slice(5) ?? ''}</span>
                  <span className="text-[9px] text-slate-700">{daily[daily.length - 1]?.date?.slice(5) ?? ''}</span>
                </div>
              </div>

              {/* Chart: Confidence distribution */}
              <div className="p-5 rounded-xl bg-surface-card border border-white/[0.07]">
                <h2 className="text-[11px] font-semibold text-slate-400 mb-4">Confidence Distribution</h2>
                <div className="space-y-1.5">
                  {confDist.map((b) => (
                    <div key={b.bucket} className="flex items-center gap-2">
                      <span className="text-[9px] text-slate-600 w-8 text-right flex-shrink-0">{b.bucket}%</span>
                      <Bar value={b.count} max={maxConf} color="bg-emerald-500/70" />
                      <span className="text-[9px] text-slate-600 w-6 flex-shrink-0">{b.count}</span>
                    </div>
                  ))}
                  {confDist.length === 0 && <p className="text-xs text-slate-700">No data yet</p>}
                </div>
              </div>
            </section>

            {/* Evaluation metrics */}
            {evalData && (
              <section className="p-5 rounded-xl bg-surface-card border border-white/[0.07]">
                <h2 className="text-[11px] font-semibold text-slate-400 mb-4">Evaluation Metrics (last 100 queries)</h2>
                <div className="grid grid-cols-3 gap-4 mb-5">
                  {[
                    { label: 'Avg Recall@3',    key: 'avg_recall',    color: 'text-indigo-300' },
                    { label: 'Avg Faithfulness', key: 'avg_faith',    color: 'text-emerald-300' },
                    { label: 'Avg Relevance',    key: 'avg_relevance', color: 'text-amber-300' },
                  ].map(({ label, key, color }) => (
                    <div key={key} className="text-center">
                      <p className={`text-xl font-bold ${color}`}>{pct(evalData.averages[key] ?? 0)}</p>
                      <p className="text-[10px] text-slate-600 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="text-slate-600 border-b border-white/[0.05]">
                        <th className="text-left py-1.5 pr-4 font-medium">Query</th>
                        <th className="text-right py-1.5 pr-3 font-medium">Recall@3</th>
                        <th className="text-right py-1.5 pr-3 font-medium">Faithfulness</th>
                        <th className="text-right py-1.5 font-medium">Relevance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evalData.recent.map((r, i) => (
                        <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                          <td className="py-1.5 pr-4 text-slate-400 truncate max-w-xs">{r.query.slice(0, 60)}</td>
                          <td className="py-1.5 pr-3 text-right text-indigo-300">{pct(r.recall_at_k)}</td>
                          <td className="py-1.5 pr-3 text-right text-emerald-300">{pct(r.faithfulness)}</td>
                          <td className="py-1.5 text-right text-amber-300">{pct(r.relevance_score)}</td>
                        </tr>
                      ))}
                      {evalData.recent.length === 0 && (
                        <tr><td colSpan={4} className="py-4 text-center text-slate-700">No queries yet</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* Top 20 interactions */}
            <section className="p-5 rounded-xl bg-surface-card border border-white/[0.07]">
              <h2 className="text-[11px] font-semibold text-slate-400 mb-4">Top 20 Interactions</h2>
              <div className="space-y-2">
                {topQ.map((q, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-[10px] text-slate-700 w-5 text-right flex-shrink-0">{i + 1}</span>
                    <span className="text-[11px] text-slate-400 flex-1 truncate">{q.query}</span>
                    <Bar value={q.frequency} max={maxFreq} />
                    <span className="text-[10px] text-slate-500 w-6 text-right flex-shrink-0">{q.frequency}×</span>
                  </div>
                ))}
                {topQ.length === 0 && <p className="text-xs text-slate-700">No interactions yet</p>}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}

export default AdminDashboard
