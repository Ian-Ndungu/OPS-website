import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, kes, label } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, Empty, ErrorBox, Field, Modal, Progress, Spinner, Stat, useAction, useAsync, useToast } from '../components/ui'
import SeatRing from '../components/SeatRing'

const STEPS = [
  ['Apply', 'Send your gamer tag, CODM UID and a clan screenshot. Admins check your membership.'],
  ['Get a seat', 'Approved members are placed by a fair, recorded random draw. Extra applicants join a waiting list.'],
  ['Accept the terms', 'When a cohort fills, every member accepts the terms before it starts.'],
  ['Pay monthly', 'Pay through M-Pesa each month. A payment counts only after the provider confirms it.'],
  ['Get paid together', 'After the last contribution is reconciled and two admins approve, everyone is paid at once.'],
]

/* ------------------------------------------------------ public landing */
export function MythicLanding() {
  const plans = useAsync(() => api.get('/api/mythic/plans'))
  const cms = useAsync(() => api.get('/api/mythic/content'))
  const { user } = useAuth()
  const [sel, setSel] = useState('A')
  const c = cms.data || {}
  const p = plans.data?.plans.find((x) => x.code === sel)
  const open = p ? Math.min(p.available_slots, p.members) : 0
  return (
    <div className="space-y-14">
      {c.banner?.text && <div className="tone-warn rounded-2xl p-4 text-center text-sm font-semibold">{c.banner.text}</div>}
      <section className="grid items-center gap-10 lg:grid-cols-[1.05fr_.95fr]">
        <div>
          <h1 className="max-w-[14ch] text-balance font-display text-5xl font-extrabold leading-[0.98] text-white sm:text-6xl lg:text-7xl">Save with your clan. Get paid together.</h1>
          <p className="mt-6 max-w-[54ch] text-lg leading-relaxed text-slate-300">{c.landing_description?.text || 'The Mythic Circle is a fixed-term savings program for verified OPS members. Everyone puts in the same amount each month, and everyone receives KSh 7,000 on the same day at the end.'}</p>
          {c.registration_announcement?.text && <p className="tone-ok mt-4 inline-block rounded-2xl px-4 py-2 text-sm font-semibold">{c.registration_announcement.text}</p>}
          <div className="mt-8 flex flex-wrap gap-3">
            {user ? <Link to="/dashboard/mythic-circle" className="btn-primary !px-6 !py-3 text-base">Apply or open my dashboard</Link> : <Link to="/login" className="btn-primary !px-6 !py-3 text-base">Log in to apply</Link>}
          </div>
        </div>
        <div className="rounded-[36px] bg-ops-card p-6 sm:p-8">
          {plans.loading && <Spinner />}<ErrorBox message={plans.error} />
          {plans.data && (
            <>
              <div className="mx-auto flex w-fit rounded-full bg-ops-raised p-1" role="group" aria-label="Choose a cohort size">
                {plans.data.plans.map((x) => (
                  <button key={x.code} onClick={() => setSel(x.code)} aria-pressed={sel === x.code}
                    className={`rounded-full px-5 py-2 text-sm font-semibold transition-colors ${sel === x.code ? 'bg-ops-accent text-ops-on-accent' : 'text-ops-mute hover:text-white'}`}>{x.members} players</button>
                ))}
              </div>
              {p && (
                <>
                  <div className="my-6" key={sel}>
                    <SeatRing seats={p.members} filled={p.members - open} open={open} size={250}>
                      <div className="num font-display text-6xl font-extrabold text-white">{open}</div>
                      <div className="text-sm text-ops-mute">of {p.members} seats open</div>
                    </SeatRing>
                  </div>
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    <div className="tile"><dt className="text-ops-mute">Each month</dt><dd className="num font-display text-2xl font-bold text-white">{kes(p.monthly_kes)}</dd></div>
                    <div className="tile"><dt className="text-ops-mute">For</dt><dd className="num font-display text-2xl font-bold text-white">{p.months} months</dd></div>
                    <div className="tile"><dt className="text-ops-mute">You put in</dt><dd className="num font-display text-2xl font-bold text-white">{kes(p.total_commitment_kes)}</dd></div>
                    <div className="tile bg-ops-accent"><dt className="text-ops-on-accent/70">You are paid</dt><dd className="num font-display text-2xl font-bold text-ops-on-accent">{kes(p.expected_payout_kes)}</dd></div>
                  </dl>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-ops-mute">
                    <span>Circle target {kes(p.cohort_target_kes)}. Proposed start {p.proposed_start ? fmtDate(p.proposed_start) : 'to be announced'}.</span>
                    <Badge status={p.registration_open ? 'approved' : 'draft'}>{p.registration_open ? 'Registration open' : 'Registration closed'}</Badge>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </section>

      {plans.data && (
        <div className="space-y-3">
          {!plans.data.live_payments && <div className="tone-warn rounded-2xl p-4 text-sm font-medium">Live payments are not switched on yet. Payments run in sandbox mode until legal and payment-provider checks are complete.</div>}
          <p className="max-w-[80ch] text-sm text-ops-mute">{plans.data.provider_fee_note} The two plans are fixed: no other sizes or amounts exist. Nobody is paid early, and there is no rotating payout order.</p>
        </div>
      )}

      <section>
        <h2 className="mb-6 font-display text-4xl font-extrabold text-white">How it works</h2>
        <ol className="grid gap-3 md:grid-cols-5">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="rounded-[28px] bg-ops-card p-5">
              <span className="num flex h-9 w-9 items-center justify-center rounded-full bg-ops-raised font-display text-lg font-extrabold text-ops-link">{i + 1}</span>
              <h3 className="mt-4 font-display text-xl font-bold text-white">{t}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ops-mute">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-[32px] bg-ops-card p-6 sm:p-8">
        <h2 className="font-display text-3xl font-bold text-white">Withdrawals, refunds and disputes</h2>
        <p className="mt-3 max-w-[70ch] leading-relaxed text-slate-300">Ordinary withdrawals are restricted once a cohort starts. You can cancel before it starts for a full refund. Exceptional circumstances such as incapacity or death, legal requirements, a cancelled cohort and disputes follow a documented process. You always get back the contributions you actually paid, and a refund that the law or the terms require cannot be denied.</p>
      </section>

      {c.faqs?.items?.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-display text-3xl font-bold text-white">Questions</h2>
          {c.faqs.items.map((f, i) => <details key={i} className="group rounded-2xl bg-ops-card p-5"><summary className="cursor-pointer font-semibold text-white">{f.q}</summary><p className="mt-2 max-w-[70ch] text-slate-400">{f.a}</p></details>)}
        </section>
      )}
      {c.policy_documents?.items?.length > 0 && (
        <section className="rounded-2xl bg-ops-card p-5"><h2 className="mb-2 font-display text-2xl font-bold text-white">Policies</h2>
          <ul className="space-y-1 text-sm">{c.policy_documents.items.map((d, i) => <li key={i}><a className="link" href={d.url} target="_blank" rel="noreferrer">{d.title}</a></li>)}</ul></section>
      )}
    </div>
  )
}

/* ------------------------------------------------- application form */
function ApplyForm({ onDone, plans, existing }) {
  const [f, setF] = useState({ gamer_tag: '', codm_uid: '', rank: '', email: '', phone: '', preferred_plan: 'A' })
  const [file, setFile] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true)
    const fd = new FormData()
    Object.entries(f).forEach(([k, v]) => fd.append(k, v)); fd.append('screenshot', file)
    try { await api.form('/api/mythic/applications', fd); onDone() } catch (x) { setErr(x.message) }
    setBusy(false)
  }
  return (
    <form onSubmit={submit} className="card space-y-5 !rounded-[32px]">
      <h2 className="font-display text-3xl font-bold text-white">{existing ? 'Resubmit your application' : 'Apply to the Mythic Circle'}</h2>
      <ErrorBox message={err} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="OPS gamer tag"><input className="input" required value={f.gamer_tag} onChange={set('gamer_tag')} /></Field>
        <Field label="CODM UID"><input className="input" required pattern="\d{6,20}" title="Digits only" value={f.codm_uid} onChange={set('codm_uid')} inputMode="numeric" /></Field>
        <Field label="Current rank"><input className="input" required value={f.rank} onChange={set('rank')} placeholder="For example, Legendary" /></Field>
        <Field label="Email"><input className="input" type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label="M-Pesa phone number"><input className="input" required value={f.phone} onChange={set('phone')} placeholder="07XXXXXXXX" inputMode="tel" /></Field>
        <Field label="Preferred cohort">
          <select className="input" value={f.preferred_plan} onChange={set('preferred_plan')}>
            {(plans || []).map((p) => <option key={p.code} value={p.code}>{p.members} players, {kes(p.monthly_kes)} a month for {p.months} months</option>)}
          </select>
        </Field>
      </div>
      <Field label="Clan membership screenshot (PNG, JPG or WebP, up to 5 MB)"><input className="input" type="file" accept="image/png,image/jpeg,image/webp" required onChange={(e) => setFile(e.target.files[0])} /></Field>
      <p className="text-sm text-ops-mute">We also use this phone number for your payout. Only verified clan members can join.</p>
      <button className="btn-primary !py-3" disabled={busy || !file}>{busy ? 'Submitting' : 'Submit application'}</button>
    </form>
  )
}

const STATUS_TEXT = {
  pending: 'Submitted. An admin will pick it up soon.', under_review: 'An admin is reviewing your clan membership evidence.',
  approved: 'Approved. You are eligible for a seat in the next draw.', rejected: 'This application was not approved.', resubmission_required: 'Resubmit with the corrections below.',
}

function Steps({ progress }) {
  const steps = [['Submitted', progress.submitted], ['Reviewed', progress.reviewed], ['Approved', progress.approved]]
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm">
      {steps.map(([t, done], i) => (
        <li key={t} className="flex items-center gap-2">
          <span className={`num flex h-7 w-7 items-center justify-center rounded-full font-bold ${done ? 'bg-ops-ok text-black' : 'bg-ops-raised text-ops-mute'}`}>{i + 1}</span>
          <span className={done ? 'font-medium text-white' : 'text-ops-mute'}>{t}</span>{i < 2 && <span className="mx-1 h-px w-6 bg-ops-line" />}
        </li>
      ))}
    </ol>
  )
}

/* ------------------------------------------------ member dashboard */
export function MythicDashboard() {
  const me = useAsync(() => api.get('/api/mythic/me'))
  const plans = useAsync(() => api.get('/api/mythic/plans'))
  const [toast, node] = useToast()
  const act = useAction(me.reload, toast)
  const [refund, setRefund] = useState(null)
  if (me.loading) return <Spinner />
  if (me.error) return <ErrorBox message={me.error} />
  const { application: app, membership: m } = me.data

  if (!app) return <div className="space-y-6"><h1 className="font-display text-5xl font-extrabold text-white">Mythic Circle</h1><ApplyForm plans={plans.data?.plans} onDone={me.reload} /></div>

  const cp = m?.cohort_progress
  const payable = m && ['active', 'contributions_in_progress'].includes(m.cohort.status)
  return (
    <div className="space-y-6">
      {node}
      <h1 className="font-display text-5xl font-extrabold text-white">My Mythic Circle</h1>

      {!m && (
        <div className="card space-y-4 !rounded-[32px]">
          <div className="flex flex-wrap items-center gap-3"><h2 className="font-display text-3xl font-bold text-white">Your application</h2><Badge status={app.status}>{app.status}</Badge></div>
          <p className="text-slate-300">{STATUS_TEXT[app.status]}</p>
          {app.note && <p className="tile text-sm"><span className="font-semibold text-white">Note from the reviewer:</span> {app.note}</p>}
          <Steps progress={app.progress} />
          {app.waitlist_position && <p className="font-medium text-ops-link">You are number {app.waitlist_position} on the waiting list.</p>}
          {app.status === 'approved' && !app.waitlist_position && <p className="text-sm text-ops-mute">We'll notify you when a draw places you in a cohort.</p>}
        </div>
      )}
      {app.status === 'resubmission_required' && <ApplyForm existing plans={plans.data?.plans} onDone={me.reload} />}

      {m && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-3xl font-bold text-white">{m.cohort.name}</h2>
              <p className="text-ops-mute">{m.cohort.capacity} members, {kes(m.cohort.monthly_kes)} a month for {m.cohort.months} months</p>
            </div>
            <Badge status={m.cohort.status}>{m.cohort.status}</Badge>
          </div>

          {m.cohort.status === 'awaiting_acceptance' && !m.terms_accepted && (
            <div className="tone-warn space-y-3 rounded-[28px] p-6">
              <h2 className="font-display text-2xl font-bold">Accept the terms to start</h2>
              <p className="max-w-[70ch] text-sm leading-relaxed">You commit to {m.cohort.months} monthly contributions of {kes(m.cohort.monthly_kes)} ({kes(m.cohort.months * m.cohort.monthly_kes)} in total) and you receive {kes(m.cohort.expected_payout_kes)} when the cohort completes. Ordinary withdrawals are restricted once the cohort starts. Refunds, disputes and exceptional circumstances follow the documented process. The cohort starts only when every member accepts.</p>
              <button className="btn-primary" onClick={() => act(() => api.post('/api/mythic/me/accept-terms'), 'Terms accepted')}>Accept the terms</button>
            </div>
          )}
          {m.cohort.status === 'awaiting_acceptance' && m.terms_accepted && <Empty>You accepted the terms. Waiting for the other members and for an admin to start the cohort.</Empty>}

          <div className="grid gap-4 lg:grid-cols-5">
            <div className="space-y-4 lg:col-span-3">
              {m.next_due ? (
                <div className="rounded-[32px] bg-ops-accent p-6 text-ops-on-accent sm:p-8">
                  <div className="text-sm font-semibold opacity-80">Next contribution, month {m.next_due.month_no}</div>
                  <div className="num mt-1 font-display text-6xl font-extrabold">{kes(m.next_due.amount_kes)}</div>
                  <div className="mt-1 font-medium">Due {fmtDate(m.next_due.due_date)}. Status: {label(m.next_due.status)}.</div>
                  <button className="mt-5 inline-flex items-center justify-center rounded-full bg-ops-bg px-6 py-3 text-base font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50" disabled={!payable}
                    onClick={() => act(() => api.post(`/api/mythic/contributions/${m.next_due.id}/pay`), 'M-Pesa prompt sent. Approve it on your phone. Your status updates after confirmation.')}>Pay with M-Pesa</button>
                  {!payable && <p className="mt-3 text-sm font-medium opacity-80">Payments open when the cohort is active.</p>}
                </div>
              ) : <Empty>No contribution is due right now.</Empty>}
              <div className="grid grid-cols-2 gap-3">
                <Stat title="You have paid in" value={kes(m.deposited_kes)} />
                <Stat title="Still to pay" value={kes(m.remaining_kes)} />
                <Stat title="You will be paid" value={kes(m.cohort.expected_payout_kes)} hint={m.provider_fee_note} />
                <Stat title="Expected completion" value={m.cohort.expected_completion ? fmtDate(m.cohort.expected_completion) : 'Not set'} hint={m.cohort.proposed_start && !m.cohort.start_date ? `Proposed start ${fmtDate(m.cohort.proposed_start)}` : undefined} />
              </div>
            </div>
            <div className="rounded-[32px] bg-ops-card p-6 lg:col-span-2">
              <h3 className="text-center font-display text-xl font-bold text-white">The whole circle</h3>
              <div className="my-4">
                <SeatRing seats={cp.capacity} filled={(cp.collected_kes / cp.target_kes) * cp.capacity} size={250}
                  label={`Circle is ${cp.percent} percent funded`}>
                  <div className="num font-display text-5xl font-extrabold text-white">{cp.percent}%</div>
                  <div className="text-sm text-ops-mute">funded</div>
                </SeatRing>
              </div>
              <p className="num text-center text-sm text-ops-mute">{kes(cp.collected_kes)} of {kes(cp.target_kes)}. {cp.members} of {cp.capacity} seats taken. Only the circle total is shown, never what others paid.</p>
            </div>
          </div>

          <section>
            <h2 className="mb-3 font-display text-2xl font-bold text-white">Your payments</h2>
            {m.timeline.length ? (
              <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {m.timeline.map((t) => (
                  <li key={t.id} className="rounded-3xl bg-ops-card p-4">
                    <div className="flex items-center justify-between"><span className="font-display text-lg font-bold text-white">Month {t.month_no}</span><Badge status={t.status}>{t.status}</Badge></div>
                    <div className="num mt-2 text-xl font-bold text-white">{kes(t.amount_kes)}</div>
                    <div className="text-sm text-ops-mute">Due {fmtDate(t.due_date)}</div>
                    {t.receipt && <button className="link mt-2 text-sm" onClick={() => downloadReceipt(t.id)}>Download receipt</button>}
                  </li>
                ))}
              </ol>
            ) : <Empty>Your payment schedule appears when the cohort starts.</Empty>}
          </section>

          <div className="flex flex-wrap items-center justify-between gap-4 rounded-[28px] bg-ops-card p-6">
            <div>
              <h2 className="font-display text-xl font-bold text-white">Payout</h2>
              <p className="mt-1 text-sm text-ops-mute">{m.payout_readiness ? 'The circle is funded and the payout is in progress.' : 'Not ready yet. Everyone is paid together once the circle is fully funded.'}</p>
              <div className="mt-2 flex items-center gap-3"><Badge status={m.payout_status}>{m.payout_status}</Badge>
                {['succeeded', 'resolved'].includes(m.payout_status) && <button className="link text-sm" onClick={() => downloadPayoutReceipt()}>Download payout receipt</button>}</div>
            </div>
            <button className="btn-ghost" onClick={() => setRefund({ kind: m.cohort.status === 'awaiting_acceptance' ? 'pre_activation_cancel' : 'exceptional', detail: '' })}>
              {m.cohort.status === 'awaiting_acceptance' ? 'Cancel my place' : 'Ask for an exceptional withdrawal'}</button>
          </div>
        </>
      )}

      {refund && (
        <Modal title="Refund or withdrawal request" onClose={() => setRefund(null)}>
          <div className="space-y-4">
            <Field label="Reason"><select className="input" value={refund.kind} onChange={(e) => setRefund({ ...refund, kind: e.target.value })}>
              {['pre_activation_cancel', 'exceptional', 'death_incapacity', 'dispute', 'legal'].map((k) => <option key={k} value={k}>{label(k)}</option>)}</select></Field>
            <Field label="What happened"><textarea className="input" rows={4} value={refund.detail} onChange={(e) => setRefund({ ...refund, detail: e.target.value })} /></Field>
            <p className="text-sm text-ops-mute">You get back the contributions you actually paid, with no penalties. An admin reviews exceptional requests and must give written reasons for any denial.</p>
            <button className="btn-primary" disabled={!refund.detail.trim()} onClick={() => act(async () => { await api.post('/api/mythic/me/refund-requests', refund); setRefund(null) }, 'Request submitted')}>Submit request</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

async function downloadReceipt(id) {
  const r = await api.get(`/api/mythic/contributions/${id}/receipt`)
  const text = `OPS MYTHIC CIRCLE: PAYMENT RECEIPT\n\nReceipt no: ${r.receipt_no}\nCohort: ${r.cohort}\nMember: ${r.member}\nMonth: ${r.month_no}\nAmount: ${kes(r.amount_kes)}\nPaid at: ${r.paid_at}\n`
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  a.download = `receipt-${r.receipt_no}.txt`
  a.click()
}

async function downloadPayoutReceipt() {
  const r = await api.get('/api/mythic/me/payout-receipt')
  const text = `OPS MYTHIC CIRCLE: PAYOUT RECEIPT\n\nReceipt no: ${r.receipt_no}\nCohort: ${r.cohort}\nMember: ${r.member}\nAmount: ${kes(r.amount_kes)}\nStatus: ${r.status}\n`
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  a.download = `payout-receipt-${r.receipt_no}.txt`
  a.click()
}
