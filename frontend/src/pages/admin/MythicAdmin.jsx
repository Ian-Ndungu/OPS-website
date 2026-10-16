import { useState } from 'react'
import { api, fmtDate, kes, label } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Badge, Empty, ErrorBox, Field, Modal, Progress, Spinner, Stat, Table, useAction, useAsync, useToast } from '../../components/ui'

const ask = (q) => window.prompt(q)

/* ------------------------------------------------------------- Overview + registration + content */
export function MythicOverview() {
  const ov = useAsync(() => api.get('/api/mythic/admin/overview'))
  const { hasRole } = useAuth()
  const o = ov.data
  return (
    <div className="space-y-8">
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Mythic Circle</h1>
      {ov.loading && <Spinner />}<ErrorBox message={ov.error} />
      {o && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat title="Total applicants" value={o.total_applicants} />
          <Stat title="Verified members" value={o.verified_members} />
          <Stat title="Active cohorts" value={o.active_cohorts} />
          <Stat title="Fully funded" value={o.fully_funded_cohorts} />
          <Stat title="Confirmed contributions" value={kes(o.total_confirmed_contributions_kes)} />
          <Stat title="Pending payments" value={o.pending_payments} />
          <Stat title="Pending payout approvals" value={o.pending_payout_approvals} />
          <Stat title="Completed payouts" value={o.completed_payouts} />
        </div>
      )}
      {hasRole('finance_admin') && <><Registration /><ContentEditor /></>}
    </div>
  )
}

function Registration() {
  const periods = useAsync(() => api.get('/api/mythic/admin/periods'))
  const [toast, node] = useToast()
  const act = useAction(periods.reload, toast)
  const [f, setF] = useState({ plan_code: 'A', opens_at: '', closes_at: '', proposed_start: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <section className="space-y-3">
      {node}
      <h2 className="font-display text-2xl font-bold text-white">Registration periods</h2>
      <div className="card grid gap-3 sm:grid-cols-2 2xl:grid-cols-5">
        <select className="input" value={f.plan_code} onChange={set('plan_code')}><option value="A">7-player (A)</option><option value="B">10-player (B)</option></select>
        <input className="input" type="datetime-local" value={f.opens_at} onChange={set('opens_at')} aria-label="Opens" />
        <input className="input" type="datetime-local" value={f.closes_at} onChange={set('closes_at')} aria-label="Closes" />
        <input className="input" type="date" value={f.proposed_start} onChange={set('proposed_start')} aria-label="Proposed start" />
        <button className="btn-primary" onClick={() => act(() => api.post('/api/mythic/admin/periods', {
          plan_code: f.plan_code, opens_at: new Date(f.opens_at).toISOString(), closes_at: new Date(f.closes_at).toISOString(), proposed_start: f.proposed_start || null }), 'Period created')}>Add period</button>
      </div>
      <Table head={['Plan', 'Opens', 'Closes', 'State', 'Draw', 'Actions']}>
        {periods.data?.map((p) => (
          <tr key={p.id}>
            <td className="px-4 py-3">{p.plan}</td><td className="px-4 py-3">{fmtDate(p.opens_at)}</td><td className="px-4 py-3">{fmtDate(p.closes_at)}</td>
            <td className="px-4 py-3"><Badge status={p.is_open ? 'approved' : 'draft'}>{p.is_open ? 'Open' : 'Closed'}</Badge></td>
            <td className="px-4 py-3 text-xs">{p.drawn_at ? `Seed ${p.draw_seed}` : 'Not drawn'}</td>
            <td className="space-x-2 px-4 py-3">
              <button className="btn-ghost" onClick={() => act(() => api.post(`/api/mythic/admin/periods/${p.id}/${p.is_open ? 'close' : 'open'}`))}>{p.is_open ? 'Close' : 'Open'}</button>
              {!p.drawn_at && <button className="btn-ghost" onClick={() => confirm('Run the random draw now? This cannot be repeated.') && act(() => api.post(`/api/mythic/admin/periods/${p.id}/draw`), 'Draw complete')}>Run fair draw</button>}
            </td>
          </tr>
        ))}
      </Table>
    </section>
  )
}

const CMS = [
  ['landing_description', 'Landing page description', (v) => v.text || '', (t) => ({ text: t })],
  ['banner', 'Banner text', (v) => v.text || '', (t) => ({ text: t })],
  ['registration_announcement', 'Registration announcement', (v) => v.text || '', (t) => ({ text: t })],
]

function ContentEditor() {
  const cms = useAsync(() => api.get('/api/mythic/content'))
  const [toast, node] = useToast()
  const act = useAction(cms.reload, toast)
  const [drafts, setDrafts] = useState({})
  const [faq, setFaq] = useState({ q: '', a: '' })
  const val = (k, get) => drafts[k] ?? get(cms.data?.[k] || {})
  const enabled = cms.data?.enrollment_enabled?.enabled !== false
  const save = (key, value) => act(() => api.put(`/api/mythic/admin/content/${key}`, { value }), 'Saved')
  return (
    <section className="space-y-3">
      {node}
      <h2 className="font-display text-2xl font-bold text-white">Content management</h2>
      <p className="text-xs text-ops-mute">Plan terms (7 players × KSh 1,000 × 7 months; 10 players × KSh 700 × 10 months) are fixed in code and cannot be edited here.</p>
      <div className="card flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm">Enrollment is <b>{enabled ? 'enabled' : 'disabled'}</b></span>
        <button className="btn-ghost" onClick={() => save('enrollment_enabled', { enabled: !enabled })}>{enabled ? 'Disable' : 'Enable'} enrollment</button>
      </div>
      {CMS.map(([key, title, get, mk]) => (
        <div key={key} className="card space-y-2">
          <Field label={title}><textarea className="input" rows={2} value={val(key, get)} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })} /></Field>
          <button className="btn-ghost" onClick={() => save(key, mk(val(key, get)))}>Save</button>
        </div>
      ))}
      <div className="card space-y-2">
        <div className="label">FAQs ({cms.data?.faqs?.items?.length || 0})</div>
        {(cms.data?.faqs?.items || []).map((x, i) => (
          <div key={i} className="flex items-start justify-between gap-2 rounded-2xl bg-ops-raised p-2 text-sm">
            <div><b>{x.q}</b><div className="text-ops-mute">{x.a}</div></div>
            <button className="btn-danger" onClick={() => save('faqs', { items: cms.data.faqs.items.filter((_, j) => j !== i) })}>Remove</button>
          </div>
        ))}
        <input className="input" placeholder="Question" value={faq.q} onChange={(e) => setFaq({ ...faq, q: e.target.value })} />
        <textarea className="input" rows={2} placeholder="Answer" value={faq.a} onChange={(e) => setFaq({ ...faq, a: e.target.value })} />
        <button className="btn-ghost" disabled={!faq.q || !faq.a} onClick={() => { save('faqs', { items: [...(cms.data?.faqs?.items || []), faq] }); setFaq({ q: '', a: '' }) }}>Add FAQ</button>
      </div>
      <div className="card space-y-2">
        <div className="label">Policy documents (title + URL)</div>
        {(cms.data?.policy_documents?.items || []).map((x, i) => <div key={i} className="text-sm">{x.title} · <span className="text-ops-mute">{x.url}</span></div>)}
        <button className="btn-ghost" onClick={() => { const title = ask('Document title'); const url = ask('Document URL (https://…)'); if (title && /^https?:\/\//.test(url || '')) save('policy_documents', { items: [...(cms.data?.policy_documents?.items || []), { title, url }] }) }}>Add policy document</button>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------- Clan verification */
export function Verification() {
  const [status, setStatus] = useState('')
  const apps = useAsync(() => api.get(`/api/mythic/admin/applications${status ? `?status=${status}` : ''}`), [status])
  const [toast, node] = useToast()
  const act = useAction(apps.reload, toast)
  const [view, setView] = useState(null)
  const review = (a, decision) => {
    const note = ['rejected', 'resubmission_required'].includes(decision) ? ask('Reason shown to the applicant (required)') : null
    if (['rejected', 'resubmission_required'].includes(decision) && !note) return
    act(() => api.post(`/api/mythic/admin/applications/${a.id}/review`, { decision, note }), `Marked ${label(decision)}`)
  }
  const openShot = async (a) => {
    const res = await fetch(a.screenshot, { headers: { Authorization: `Bearer ${localStorage.getItem('ops_token')}` } })
    setView({ a, url: URL.createObjectURL(await res.blob()) })
  }
  return (
    <div className="space-y-4">
      {node}
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Clan Verification</h1>
      <select className="input max-w-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All statuses</option>{['pending', 'under_review', 'approved', 'rejected', 'resubmission_required'].map((s) => <option key={s} value={s}>{label(s)}</option>)}
      </select>
      {apps.loading && <Spinner />}<ErrorBox message={apps.error} />
      <Table head={['Applicant', 'CODM UID', 'Rank', 'Contact', 'Plan', 'Status', 'Actions']}>
        {apps.data?.map((a) => (
          <tr key={a.id}>
            <td className="px-4 py-3 font-semibold">{a.gamer_tag}</td><td className="px-4 py-3">{a.codm_uid}</td><td className="px-4 py-3">{a.rank}</td>
            <td className="px-4 py-3 text-xs">{a.email}<br />{a.phone}</td><td className="px-4 py-3">{a.plan}</td>
            <td className="px-4 py-3"><Badge status={a.status}>{a.status}</Badge>{a.waitlist_position && <div className="text-xs text-ops-mute">Waitlist #{a.waitlist_position}</div>}</td>
            <td className="space-x-1 px-4 py-3">
              <button className="btn-ghost" onClick={() => openShot(a)}>Evidence</button>
              <button className="btn-ghost" onClick={() => review(a, 'under_review')}>Review</button>
              <button className="btn-primary" onClick={() => review(a, 'approved')}>Approve</button>
              <button className="btn-ghost" onClick={() => review(a, 'resubmission_required')}>Resubmit</button>
              <button className="btn-danger" onClick={() => review(a, 'rejected')}>Reject</button>
            </td>
          </tr>
        ))}
      </Table>
      {apps.data && !apps.data.length && <Empty>No applications.</Empty>}
      {view && <Modal title={`Clan evidence: ${view.a.gamer_tag}`} onClose={() => setView(null)}><img src={view.url} alt="Clan membership screenshot" className="w-full rounded-lg" /></Modal>}
    </div>
  )
}

/* ------------------------------------------------------------------- Cohorts */
export function Cohorts() {
  const list = useAsync(() => api.get('/api/mythic/admin/cohorts'))
  const apps = useAsync(() => api.get('/api/mythic/admin/applications?status=approved'))
  const [toast, node] = useToast()
  const act = useAction(() => { list.reload(); apps.reload() }, toast)
  const [name, setName] = useState('')
  const [open, setOpen] = useState(null)
  return (
    <div className="space-y-6">
      {node}
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Cohorts</h1>
      <div className="card flex flex-wrap gap-3">
        <input className="input max-w-xs" placeholder="Cohort name" value={name} onChange={(e) => setName(e.target.value)} />
        {[7, 10].map((size) => <button key={size} className="btn-primary" disabled={!name} onClick={() => act(() => api.post('/api/mythic/admin/cohorts', { name, size }), 'Cohort created')}>Create {size}-member cohort</button>)}
        <span className="self-center text-xs text-ops-mute">Only 7 and 10 member cohorts exist; terms are fixed.</span>
      </div>
      {list.loading && <Spinner />}<ErrorBox message={list.error} />
      <div className="grid gap-4 xl:grid-cols-2">
        {list.data?.map((c) => (
          <div key={c.cohort_id} className="card space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-display text-xl font-bold text-white">{c.name}</h2><Badge status={c.status}>{c.status}</Badge></div>
            <div className="text-sm text-ops-mute">{c.members}/{c.capacity} members · {kes(c.monthly_kes)} × {c.months} · start {fmtDate(c.start_date)}</div>
            <Progress value={c.collected_kes} max={c.target_kes} />
            <div className="text-xs text-ops-mute">{kes(c.collected_kes)} / {kes(c.target_kes)}</div>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost" onClick={() => setOpen(c.cohort_id)}>Financials</button>
              {c.status === 'registration_open' && <>
                <AssignButton cohort={c} apps={apps.data} act={act} />
                <button className="btn-ghost" onClick={() => act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/promote-waitlist`), 'Waitlist promoted')}>Promote waitlist</button></>}
              {c.status === 'awaiting_acceptance' && <button className="btn-primary" onClick={() => { const d = ask('Start date (YYYY-MM-DD)'); d && act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/activate`, { start_date: d }), 'Cohort activated') }}>Activate</button>}
              {['active', 'contributions_in_progress', 'fully_funded'].includes(c.status) && <button className="btn-ghost" onClick={() => { const r = ask('Reason for pause (recorded)'); r && act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/pause`, { reason: r }), 'Paused') }}>Pause</button>}
              {c.status === 'paused' && <button className="btn-ghost" onClick={() => { const r = ask('Reason for resuming'); r && act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/resume`, { reason: r }), 'Resumed') }}>Resume</button>}
              {!['completed', 'cancelled'].includes(c.status) && <button className="btn-danger" onClick={() => { const r = ask('Cancel cohort and refund all members in full? Enter reason:'); r && act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/cancel`, { reason: r }), 'Cohort cancelled; refunds queued') }}>Cancel</button>}
            </div>
          </div>
        ))}
      </div>
      {open && <CohortFinancials id={open} onClose={() => setOpen(null)} act={act} />}
    </div>
  )
}

function AssignButton({ cohort, apps, act }) {
  const eligible = (apps || []).filter((a) => (a.plan === cohort.plan) && !a.assigned)
  return (
    <select className="input w-full sm:w-auto" defaultValue="" onChange={(e) => e.target.value && act(() => api.post(`/api/mythic/admin/cohorts/${cohort.cohort_id}/assign`, { application_id: Number(e.target.value) }), 'Member assigned')}>
      <option value="">Assign member…</option>
      {eligible.map((a) => <option key={a.id} value={a.id}>{a.gamer_tag}</option>)}
    </select>
  )
}

function CohortFinancials({ id, onClose, act }) {
  const d = useAsync(() => api.get(`/api/mythic/admin/cohorts/${id}`), [id])
  return (
    <Modal title="Funding status" onClose={onClose}>
      {d.loading && <Spinner />}<ErrorBox message={d.error} />
      {d.data && (() => { const r = d.data.reconciliation; return (
        <div className="space-y-3 text-sm">
          <div>Target {kes(r.target_kes)} · ledger net {kes(r.ledger_net_kes)} · payout liability {kes(r.total_payout_liability_kes)}</div>
          <ul className="space-y-1">{Object.entries(r.checks).map(([k, v]) => <li key={k} className="py-0.5"><span className={`badge ${v ? 'tone-ok' : 'tone-mute'}`}>{v ? 'Met' : 'Not met'}</span> {label(k)}</li>)}</ul>
          <div>Open exceptions: {r.open_exceptions}</div>
          {d.data.outstanding.length > 0 && <div><div className="label">Outstanding</div>{d.data.outstanding.map((o, i) => <div key={i}>Member #{o.member_id} · month {o.month_no} · {kes(o.amount_kes)} · <Badge status={o.status}>{o.status}</Badge></div>)}</div>}
          <button className="btn-ghost" onClick={() => act(() => api.post(`/api/mythic/admin/cohorts/${id}/recheck-funding`), 'Funding re-checked')}>Re-check funding</button>
        </div>) })()}
    </Modal>
  )
}

/* ------------------------------------------------------------- Contributions */
export function Contributions() {
  const ex = useAsync(() => api.get('/api/mythic/admin/exceptions'))
  const ledger = useAsync(() => api.get('/api/mythic/admin/ledger'))
  const audit = useAsync(() => api.get('/api/mythic/admin/audit'))
  const refunds = useAsync(() => api.get('/api/mythic/admin/refunds'))
  const reload = () => { ex.reload(); ledger.reload(); audit.reload(); refunds.reload() }
  const [toast, node] = useToast()
  const act = useAction(reload, toast)
  return (
    <div className="space-y-8">
      {node}
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Contributions &amp; finance</h1>

      <section className="space-y-2">
        <h2 className="font-display text-2xl font-bold text-white">Payment exceptions &amp; failures</h2>
        <Table head={['Cohort', 'Kind', 'Detail', 'State', '']}>
          {ex.data?.map((e) => (
            <tr key={e.id}><td className="px-4 py-3">#{e.cohort_id}</td><td className="px-4 py-3">{label(e.kind)}</td><td className="px-4 py-3">{e.detail}</td>
              <td className="px-4 py-3"><Badge status={e.resolved ? 'resolved' : 'pending'}>{e.resolved ? 'Resolved' : 'Open'}</Badge></td>
              <td className="px-4 py-3">{!e.resolved && <button className="btn-ghost" onClick={() => { const r = ask('Resolution / evidence note'); r && act(() => api.post(`/api/mythic/admin/exceptions/${e.id}/resolve`, { resolution: r }), 'Resolved') }}>Resolve</button>}</td></tr>
          ))}
        </Table>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-2xl font-bold text-white">Refund requests</h2>
        <Table head={['Member', 'Reason', 'Amount', 'Status', 'Actions']}>
          {refunds.data?.map((r) => (
            <tr key={r.id}><td className="px-4 py-3">#{r.member_id}</td><td className="px-4 py-3">{label(r.kind)}<div className="text-xs text-ops-mute">{r.detail}</div></td>
              <td className="px-4 py-3">{kes(r.calculated_kes)}</td><td className="px-4 py-3"><Badge status={r.status === 'requested' ? 'pending' : r.status}>{r.status}</Badge></td>
              <td className="space-x-1 px-4 py-3">
                {r.status === 'requested' && <>
                  <button className="btn-primary" onClick={() => act(() => api.post(`/api/mythic/admin/refunds/${r.id}/decision`, { approve: true }), 'Approved')}>Approve</button>
                  <button className="btn-danger" onClick={() => { const reason = ask('Written reason for denial (required)'); reason && act(() => api.post(`/api/mythic/admin/refunds/${r.id}/decision`, { approve: false, reason }), 'Denied') }}>Deny</button></>}
                {r.status === 'approved' && <button className="btn-primary" onClick={() => { const ref = ask('Provider transaction reference of the refund'); ref && act(() => api.post(`/api/mythic/admin/refunds/${r.id}/paid`, { provider_ref: ref }), 'Marked paid') }}>Record refund paid</button>}
              </td></tr>
          ))}
        </Table>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-2xl font-bold text-white">Ledger (append-only)</h2>
        <Table head={['#', 'Cohort', 'Kind', 'Dir', 'Amount', 'Reference', 'When']}>
          {ledger.data?.map((e) => <tr key={e.id}><td className="px-4 py-2">{e.id}</td><td className="px-4 py-2">#{e.cohort_id}</td><td className="px-4 py-2">{label(e.kind)}</td><td className="px-4 py-2">{e.direction}</td><td className="px-4 py-2">{kes(e.amount_kes)}</td><td className="px-4 py-2 text-xs">{e.ref}</td><td className="px-4 py-2 text-xs">{fmtDate(e.created_at)}</td></tr>)}
        </Table>
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-2xl font-bold text-white">Financial audit trail</h2>
        <Table head={['When', 'Actor', 'Action', 'Entity']}>
          {audit.data?.map((a) => <tr key={a.id}><td className="px-4 py-2 text-xs">{new Date(a.at).toLocaleString()}</td><td className="px-4 py-2">{a.actor_id ?? 'system'}</td><td className="px-4 py-2">{a.action}</td><td className="px-4 py-2">{a.entity} {a.entity_id}</td></tr>)}
        </Table>
      </section>
    </div>
  )
}

/* ------------------------------------------------------------------ Payouts */
export function Payouts() {
  const batches = useAsync(() => api.get('/api/mythic/admin/payout-batches'))
  const cohorts = useAsync(() => api.get('/api/mythic/admin/cohorts'))
  const { user } = useAuth()
  const [toast, node] = useToast()
  const act = useAction(() => { batches.reload(); cohorts.reload() }, toast)
  const funded = cohorts.data?.filter((c) => c.status === 'fully_funded') || []
  return (
    <div className="space-y-6">
      {node}
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Payouts</h1>
      <p className="text-sm text-ops-mute">Two different administrators must approve a locked manifest before funds move. Amounts and destinations cannot be changed; any change needs a new batch and new approvals.</p>
      {funded.length > 0 && (
        <section className="space-y-2"><h2 className="font-display text-2xl font-bold text-white">Fully funded cohorts</h2>
          {funded.map((c) => <div key={c.cohort_id} className="card flex flex-wrap items-center justify-between gap-3"><span>{c.name} · {kes(c.collected_kes)}</span>
            <button className="btn-primary" onClick={() => act(() => api.post(`/api/mythic/admin/cohorts/${c.cohort_id}/payout-batch`), 'Payout batch requested for approval')}>Request payout approval</button></div>)}
        </section>
      )}
      {batches.loading && <Spinner />}<ErrorBox message={batches.error} />
      {batches.data?.map((b) => {
        const myVote = b.approvals.find((a) => a.admin_id === user.id)
        const approvals = b.approvals.filter((a) => a.decision === 'approve').length
        return (
          <div key={b.id} className="card space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-display text-xl font-bold text-white">Batch #{b.id} · cohort #{b.cohort_id}</h2>
              <Badge status={b.status}>{b.status}</Badge>
            </div>
            <div className="text-sm">Total liability <b>{kes(b.total_kes)}</b> · {b.manifest.items.length} beneficiaries · approvals {approvals}/2 <span className="text-xs text-ops-mute">· manifest {b.manifest_hash.slice(0, 12)}…</span></div>
            <ul className="text-sm">{Object.entries(b.reconciliation.checks).map(([k, v]) => <li key={k} className="py-0.5"><span className={`badge ${v ? 'tone-ok' : 'tone-bad'}`}>{v ? 'Met' : 'Not met'}</span> {label(k)}</li>)}</ul>
            <Table head={['Member', 'Phone', 'Amount', 'Status', 'Receipt', '']}>
              {b.payouts.map((p) => {
                const item = b.manifest.items.find((i) => i.member_id === p.member_id)
                return <tr key={p.id}><td className="px-4 py-2">#{p.member_id}</td><td className="px-4 py-2">{item?.phone}</td><td className="px-4 py-2">{kes(p.amount_kes)}</td>
                  <td className="px-4 py-2"><Badge status={p.status}>{p.status}</Badge></td><td className="px-4 py-2 text-xs">{p.receipt}</td>
                  <td className="space-x-1 px-4 py-2">
                    {p.status === 'failed' && <button className="btn-ghost" onClick={() => act(() => api.post(`/api/mythic/admin/payouts/${p.id}/retry`), 'Retry submitted')}>Retry</button>}
                    {['failed', 'submitted'].includes(p.status) && <button className="btn-ghost" onClick={() => { const n = ask('Settlement note with evidence reference (min 10 chars)'); n && act(() => api.post(`/api/mythic/admin/payouts/${p.id}/resolve`, { note: n }), 'Resolved') }}>Resolve</button>}
                  </td></tr>
              })}
            </Table>
            <div className="flex flex-wrap gap-2">
              {b.status === 'pending_approval' && !myVote && <>
                <button className="btn-primary" onClick={() => act(() => api.post(`/api/mythic/admin/payout-batches/${b.id}/decision`, { decision: 'approve' }), 'Your approval recorded')}>Approve manifest</button>
                <button className="btn-danger" onClick={() => { const n = ask('Reason for rejection'); n && act(() => api.post(`/api/mythic/admin/payout-batches/${b.id}/decision`, { decision: 'reject', note: n }), 'Batch rejected') }}>Reject</button></>}
              {b.status === 'pending_approval' && myVote && <span className="text-sm text-ops-mute">You have voted. Waiting for a second administrator.</span>}
              {b.status === 'approved' && <button className="btn-primary" onClick={() => confirm('Submit ALL payouts now?') && act(() => api.post(`/api/mythic/admin/payout-batches/${b.id}/execute`), 'Bulk payout submitted')}>Execute bulk payout</button>}
            </div>
          </div>
        )
      })}
      {batches.data && !batches.data.length && <Empty>No payout batches yet.</Empty>}
    </div>
  )
}
