import { useState } from 'react'
import { api, fmtDate } from '../../lib/api'
import { Empty, ErrorBox, Spinner, useAsync } from '../../components/ui'

export default function AccountsAdmin() {
  const data = useAsync(() => api.get('/api/auth/admin/accounts'))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const review = async (id, approved) => {
    setBusy(true); setError('')
    try { await api.post(`/api/auth/admin/accounts/${id}/review`, { approved }); data.reload() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  return <div className="space-y-6"><h1 className="font-display text-3xl sm:text-4xl font-extrabold">Account approvals</h1><p className="text-ops-mute">New accounts cannot log in until approved here. Check the applicant’s details before granting access. Clan membership and Mythic verification are reviewed separately.</p><ErrorBox message={error || data.error} />
    {data.loading ? <Spinner /> : data.data?.length ? data.data.map((u) => <article key={u.id} className="tile flex flex-wrap items-center justify-between gap-4"><div className="min-w-0"><h2 className="break-words text-xl font-bold">{u.gamer_tag}</h2><p className="break-words text-ops-mute">{u.email}</p><p className="text-sm text-ops-mute">Registered {fmtDate(u.created_at)}</p></div><div className="flex flex-wrap gap-3"><button className="btn-primary" disabled={busy} onClick={() => review(u.id, true)}>Approve account</button><button className="btn-ghost" disabled={busy} onClick={() => review(u.id, false)}>Reject</button></div></article>) : !data.error && <Empty>No accounts awaiting approval.</Empty>}
  </div>
}
