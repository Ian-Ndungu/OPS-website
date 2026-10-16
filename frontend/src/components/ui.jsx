import { useCallback, useEffect, useState } from 'react'

export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }))
    try { setState({ loading: false, data: await fn(), error: null }) }
    catch (e) { setState({ loading: false, data: null, error: e.message }) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { ...state, reload: run }
}

export const Spinner = () => (
  <div className="space-y-3 py-6" role="status" aria-label="Loading">
    {[70, 90, 55].map((w) => <div key={w} className="h-4 animate-pulse rounded-full bg-ops-raised" style={{ width: `${w}%` }} />)}
  </div>
)
export const ErrorBox = ({ message }) => message ? <div role="alert" className="tone-bad rounded-2xl p-4 text-sm font-medium">{message}</div> : null
export const Empty = ({ children }) => <div className="rounded-3xl bg-ops-card p-8 text-center text-sm text-ops-mute">{children}</div>

export function Progress({ value, max = 100 }) {
  const pct = Math.max(0, Math.min(100, max ? (value / max) * 100 : 0))
  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-ops-raised" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-ops-accent transition-[width] duration-700" style={{ width: `${pct}%` }} />
    </div>
  )
}

const OK = ['paid', 'approved', 'completed', 'published', 'succeeded', 'resolved', 'registration_open', 'active', 'accepted']
const WARN = ['pending', 'pending_approval', 'awaiting_acceptance', 'queued', 'submitted', 'requested', 'scheduled', 'payout_approval_pending', 'processing_payouts', 'contributions_in_progress', 'fully_funded', 'filled', 'not_started']
const BAD = ['failed', 'overdue', 'rejected', 'cancelled', 'reversed', 'disputed', 'denied', 'needs_resolution']
const INFO = ['under_review', 'review', 'upcoming']
function tone(status) {
  const s = String(status).toLowerCase().replace(/ /g, '_')
  if (OK.includes(s)) return 'tone-ok'
  if (BAD.includes(s)) return 'tone-bad'
  if (INFO.includes(s)) return 'tone-info'
  if (WARN.includes(s)) return 'tone-warn'
  return 'tone-mute'
}
const sentence = (s) => { const t = String(s).replace(/_/g, ' ').toLowerCase(); return t.charAt(0).toUpperCase() + t.slice(1) }
export const Badge = ({ children, status }) => (
  <span className={`badge ${tone(status || children)}`}>{typeof children === 'string' ? sentence(children) : children}</span>
)

export const Stat = ({ title, value, hint }) => (
  <div className="tile">
    <div className="text-sm font-medium text-ops-mute">{title}</div>
    <div className="num mt-1 font-display text-3xl font-bold text-white">{value}</div>
    {hint && <div className="mt-1 text-xs leading-snug text-ops-mute">{hint}</div>}
  </div>
)

export function Field({ label: l, children }) {
  return <label className="block min-w-0"><span className="label">{l}</span>{children}</label>
}

export function Table({ head, children }) {
  return (
    <div className="max-w-full overflow-x-auto overscroll-x-contain rounded-3xl bg-ops-card" role="region" aria-label="Scrollable table" tabIndex={0}>
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="text-ops-mute">
          <tr>{head.map((h) => <th key={h} className="px-4 py-3.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-ops-line/60 [&>tr:hover]:bg-ops-raised/60">{children}</tbody>
      </table>
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[92dvh] min-w-0 w-full max-w-xl overflow-y-auto overscroll-contain rounded-[28px] bg-ops-card p-4 sm:p-6" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <h3 className="font-display text-2xl font-bold text-white">{title}</h3>
          <button className="btn-ghost shrink-0 !px-3 !py-1.5" onClick={onClose} aria-label="Close">Close</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function useToast() {
  const [msg, setMsg] = useState(null)
  useEffect(() => { if (msg) { const t = setTimeout(() => setMsg(null), 4000); return () => clearTimeout(t) } }, [msg])
  const node = msg ? (
    <div role="status" className={`fixed bottom-5 left-1/2 z-50 w-max max-w-[calc(100vw-2rem)] -translate-x-1/2 break-words rounded-2xl px-5 py-3 text-sm font-semibold shadow-2xl ${msg.err ? 'bg-ops-bad text-black' : 'bg-ops-accent text-ops-on-accent'}`}>{msg.text}</div>
  ) : null
  return [(text, err = false) => setMsg({ text, err }), node]
}

/** Wrap an admin action: run it, toast result, reload. */
export function useAction(reload, toast) {
  return async (fn, ok = 'Done') => {
    try { await fn(); toast(ok); reload && reload() } catch (e) { toast(e.message, true) }
  }
}
