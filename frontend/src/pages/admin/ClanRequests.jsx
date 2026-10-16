import { useEffect, useState } from 'react'
import { api, fmtDate, getToken } from '../../lib/api'
import { Badge, Empty, ErrorBox, Field, Spinner, useAsync } from '../../components/ui'

function Screenshot({ id }) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true, objectUrl
    const controller = new AbortController()
    fetch(`/api/clan/admin/requests/${id}/screenshot`, { headers: { Authorization: `Bearer ${getToken()}` }, signal: controller.signal })
      .then(async (r) => { if (!r.ok) throw new Error('Could not load screenshot'); return r.blob() })
      .then((blob) => { if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) } })
      .catch((e) => { if (active) setError(e.message) })
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [id])
  return <div><ErrorBox message={error} />{url ? <a href={url} target="_blank" rel="noreferrer"><img className="max-h-96 rounded-2xl object-contain" src={url} alt="Applicant’s updated game profile" /></a> : !error && <Spinner />}</div>
}

function RequestCard({ row, reload }) {
  const [note, setNote] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const review = async (status) => {
    setBusy(true); setError('')
    try { await api.post(`/api/clan/admin/requests/${row.id}/review`, { status, note }); reload() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  return <article className="tile space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-display text-2xl font-bold">{row.gamer_tag} <span className="text-sm text-ops-mute">#{row.id}</span></h2><Badge>{row.status}</Badge></div>
    <dl className="grid gap-3 text-sm sm:grid-cols-2">{[['Game', row.game], ['Player ID', row.player_id], ['Clan tag', row.clan_tag], ['Email', row.email], ['Contact', row.contact], ['Submitted', fmtDate(row.created_at)]].map(([label, value]) => <div key={label}><dt className="text-ops-mute">{label}</dt><dd className="break-words font-medium">{value}</dd></div>)}</dl>
    <p className="whitespace-pre-wrap break-words">{row.message}</p>
    <button className="btn-ghost" onClick={() => setShow(!show)}>{show ? 'Hide screenshot' : 'View profile screenshot'}</button>
    {show && <Screenshot id={row.id} />}
    <ErrorBox message={error} />
    {row.status === 'pending' ? <><Field label="Review note (internal)"><textarea className="input" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /></Field><div className="flex flex-wrap gap-3"><button disabled={busy} className="btn-primary" onClick={() => review('approved')}>Approve</button><button disabled={busy} className="btn-ghost" onClick={() => review('rejected')}>Reject</button></div></> : <p className="text-sm text-ops-mute">Reviewed {fmtDate(row.reviewed_at)}{row.review_note && ` · ${row.review_note}`}</p>}
  </article>
}

export default function ClanRequests() {
  const [status, setStatus] = useState('pending')
  const data = useAsync(() => api.get(`/api/clan/admin/requests?status=${status}`), [status])
  return <div className="space-y-6"><h1 className="font-display text-3xl sm:text-4xl font-extrabold">Clan join requests</h1><p className="text-ops-mute">Review public applications and confirm the updated name and clan tag in each screenshot. Approval records clan admission; website accounts are reviewed separately.</p>
    <Field label="Filter requests"><select className="input max-w-xs" value={status} onChange={(e) => setStatus(e.target.value)}>{['pending', 'approved', 'rejected', 'all'].map((s) => <option key={s} value={s}>{s}</option>)}</select></Field>
    <ErrorBox message={data.error} />{data.loading ? <Spinner /> : data.data?.length ? data.data.map((row) => <RequestCard key={row.id} row={row} reload={data.reload} />) : !data.error && <Empty>No {status === 'all' ? '' : status} requests.</Empty>}
  </div>
}
