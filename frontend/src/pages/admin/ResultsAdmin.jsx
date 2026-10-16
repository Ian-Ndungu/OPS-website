import { useState } from 'react'
import { api, fmtDate, label } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Badge, ErrorBox, Field, Modal, Spinner, Table, useAction, useAsync, useToast } from '../../components/ui'
import { Podium, Standings } from '../../components/Leaderboard'

const emptyEntry = () => ({ team_id: '', placement: '', kills: 0, placement_points: 0, kill_points: 0 })

export default function ResultsAdmin() {
  const list = useAsync(() => api.get('/api/admin/results'))
  const teams = useAsync(() => api.get('/api/teams'))
  const [sel, setSel] = useState(null)
  const [toast, node] = useToast()
  const act = useAction(list.reload, toast)
  const [nt, setNt] = useState({ name: '', game: 'CODM', mode: 'battle_royale', game_mode: '', starts_on: '' })
  const [team, setTeam] = useState('')
  return (
    <div className="space-y-6">
      {node}
      <h1 className="font-display text-5xl font-extrabold text-white">Tournament Results</h1>
      <div className="card space-y-3">
        <h2 className="font-display text-xl font-bold text-white">New tournament</h2>
        <div className="grid gap-3 sm:grid-cols-5">
          <input className="input" placeholder="Name" value={nt.name} onChange={(e) => setNt({ ...nt, name: e.target.value })} />
          <input className="input" placeholder="Game" value={nt.game} onChange={(e) => setNt({ ...nt, game: e.target.value })} />
          <select className="input" value={nt.mode} onChange={(e) => setNt({ ...nt, mode: e.target.value })}><option value="battle_royale">Battle Royale</option><option value="multiplayer">Multiplayer</option></select>
          <input className="input" placeholder="Game mode (e.g. Hardpoint)" value={nt.game_mode} onChange={(e) => setNt({ ...nt, game_mode: e.target.value })} />
          <input className="input" type="date" value={nt.starts_on} onChange={(e) => setNt({ ...nt, starts_on: e.target.value })} />
        </div>
        <button className="btn-primary" disabled={!nt.name || !nt.starts_on} onClick={() => act(() => api.post('/api/admin/results/tournaments', { ...nt, game_mode: nt.game_mode || null }), 'Tournament created')}>Create</button>
        <div className="flex gap-2 border-t border-ops-line/60 pt-3">
          <input className="input max-w-xs" placeholder="Add team name" value={team} onChange={(e) => setTeam(e.target.value)} />
          <button className="btn-ghost" disabled={!team} onClick={() => act(async () => { await api.post('/api/admin/teams', { name: team }); setTeam(''); teams.reload() }, 'Team added')}>Add team</button>
        </div>
      </div>
      {list.loading && <Spinner />}<ErrorBox message={list.error} />
      <Table head={['Tournament', 'Game', 'Mode', 'Date', 'Status', 'Rev', '']}>
        {list.data?.map((t) => (
          <tr key={t.id}><td className="px-4 py-3 font-semibold">{t.name}</td><td className="px-4 py-3">{t.game}</td><td className="px-4 py-3">{label(t.mode)}</td>
            <td className="px-4 py-3">{fmtDate(t.starts_on)}</td><td className="px-4 py-3"><Badge status={t.pub_status}>{t.pub_status}</Badge></td><td className="px-4 py-3">{t.revision}</td>
            <td className="px-4 py-3"><button className="btn-ghost" onClick={() => setSel(t.id)}>Manage</button></td></tr>
        ))}
      </Table>
      {sel && <Manage id={sel} teams={teams.data || []} onClose={() => { setSel(null); list.reload() }} />}
    </div>
  )
}

function Manage({ id, teams, onClose }) {
  const t = useAsync(() => api.get(`/api/admin/results/${id}`), [id])
  const revs = useAsync(() => api.get(`/api/admin/results/${id}/revisions`), [id])
  const { hasRole } = useAuth()
  const [toast, node] = useToast()
  const act = useAction(() => { t.reload(); revs.reload() }, toast)
  const [form, setForm] = useState(null) // {editing:matchNo|null, ...}
  const d = t.data
  const canPublish = hasRole('results_admin')
  const published = d?.pub_status === 'published'

  const startNew = () => {
    const n = (d.matches.at(-1)?.match_no || 0) + 1
    setForm(d.mode === 'battle_royale'
      ? { match_no: n, game_mode: d.game_mode || '', mvp_player: '', reason: '', entries: [emptyEntry(), emptyEntry()] }
      : { match_no: n, game_mode: d.game_mode || '', mvp_player: '', reason: '', team_a_id: '', team_b_id: '', score_a: 0, score_b: 0 })
  }
  const edit = (m) => setForm({ editing: m.match_no, match_no: m.match_no, game_mode: m.game_mode || '', mvp_player: m.mvp_player || '', reason: '',
    ...(d.mode === 'battle_royale' ? { entries: m.entries.map((e) => ({ team_id: e.team_id, placement: e.placement, kills: e.kills, placement_points: e.placement_points, kill_points: e.kill_points })) }
      : { team_a_id: m.team_a_id, team_b_id: m.team_b_id, score_a: m.score_a, score_b: m.score_b }) })

  const upload = async (file) => {
    const fd = new FormData(); fd.append('file', file)
    const r = await api.form(`/api/admin/results/${id}/screenshot`, fd)
    setForm((f) => ({ ...f, screenshot_path: r.path }))
  }
  const save = () => {
    const num = (v) => (v === '' ? null : Number(v))
    const body = { ...form, game_mode: form.game_mode || null, mvp_player: form.mvp_player || null, reason: form.reason || null }
    delete body.editing
    if (form.entries) body.entries = form.entries.map((e) => ({ team_id: Number(e.team_id), placement: Number(e.placement), kills: Number(e.kills), placement_points: Number(e.placement_points), kill_points: Number(e.kill_points) }))
    else { body.team_a_id = num(form.team_a_id); body.team_b_id = num(form.team_b_id); body.score_a = Number(form.score_a); body.score_b = Number(form.score_b) }
    act(async () => {
      if (form.editing) await api.put(`/api/admin/results/${id}/matches/${form.editing}`, body)
      else await api.post(`/api/admin/results/${id}/matches`, body)
      setForm(null)
    }, 'Match saved')
  }
  const status = (s) => act(() => api.post(`/api/admin/results/${id}/status`, { status: s }), `Moved to ${s}`)
  const setEntry = (i, k, v) => setForm({ ...form, entries: form.entries.map((e, j) => (j === i ? { ...e, [k]: v } : e)) })
  const TeamSelect = ({ value, onChange }) => <select className="input" value={value} onChange={onChange}><option value="">Team…</option>{teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>

  return (
    <Modal title={d ? d.name : 'Results'} onClose={onClose}>
      {node}
      {t.loading && <Spinner />}<ErrorBox message={t.error} />
      {d && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2"><Badge status={d.pub_status}>{d.pub_status}</Badge><span className="text-sm text-ops-mute">{label(d.mode)} · revision {d.revision}</span></div>
          <div className="flex flex-wrap gap-2">
            {d.pub_status === 'draft' && <button className="btn-ghost" onClick={() => status('review')}>Submit for review</button>}
            {d.pub_status === 'review' && <button className="btn-ghost" onClick={() => status('draft')}>Back to draft</button>}
            {d.pub_status === 'review' && canPublish && <button className="btn-primary" onClick={() => status('published')}>Publish</button>}
            {['published', 'review', 'draft'].includes(d.pub_status) && canPublish && <button className="btn-danger" onClick={() => confirm('Archive these results? They disappear from the public site.') && status('archived')}>Archive</button>}
            {d.pub_status !== 'archived' && <button className="btn-primary" onClick={startNew}>Add match</button>}
          </div>
          {published && <p className="tone-warn rounded-2xl p-3 text-sm font-medium">Published results: every correction needs a reason and is saved in the revision history.</p>}

          <div className="label">Standings preview (calculated from entered results)</div>
          {d.standings.length ? <><Podium top={d.standings.slice(0, 3)} /><Standings rows={d.standings} mode={d.mode} /></> : <p className="text-sm text-ops-mute">No matches yet.</p>}

          <div className="flex items-center gap-2"><Field label="Tournament MVP"><input className="input" defaultValue={d.mvp_player || ''} id="mvp" /></Field>
            <button className="btn-ghost mt-5" onClick={() => { const reason = published ? window.prompt('Correction reason (required)') : null; if (published && !reason) return; act(() => api.put(`/api/admin/results/${id}/mvp`, { mvp_player: document.getElementById('mvp').value || null, reason }), 'MVP saved') }}>Save MVP</button></div>

          {d.matches.map((m) => (
            <div key={m.match_no} className="flex items-center justify-between rounded-2xl bg-ops-raised p-3 text-sm">
              <span>Match {m.match_no} · winner {m.winner}</span>
              {d.pub_status !== 'archived' && <button className="btn-ghost" onClick={() => edit(m)}>Edit</button>}
            </div>
          ))}

          {form && (
            <div className="space-y-3 rounded-2xl bg-ops-raised p-4">
              <h3 className="font-display text-lg font-bold text-white">{form.editing ? `Edit match ${form.editing}` : 'New match'}</h3>
              <div className="grid grid-cols-3 gap-2">
                <Field label="Match #"><input className="input" type="number" min={1} disabled={!!form.editing} value={form.match_no} onChange={(e) => setForm({ ...form, match_no: Number(e.target.value) })} /></Field>
                <Field label="Game mode"><input className="input" value={form.game_mode} onChange={(e) => setForm({ ...form, game_mode: e.target.value })} /></Field>
                <Field label="Match MVP"><input className="input" value={form.mvp_player} onChange={(e) => setForm({ ...form, mvp_player: e.target.value })} /></Field>
              </div>
              {form.entries ? (
                <div className="space-y-2">
                  {form.entries.map((e, i) => (
                    <div key={i} className="grid grid-cols-5 gap-1">
                      <TeamSelect value={e.team_id} onChange={(x) => setEntry(i, 'team_id', x.target.value)} />
                      <input className="input" type="number" min={1} placeholder="Place" value={e.placement} onChange={(x) => setEntry(i, 'placement', x.target.value)} />
                      <input className="input" type="number" min={0} placeholder="Kills" value={e.kills} onChange={(x) => setEntry(i, 'kills', x.target.value)} />
                      <input className="input" type="number" min={0} placeholder="Place pts" value={e.placement_points} onChange={(x) => setEntry(i, 'placement_points', x.target.value)} />
                      <input className="input" type="number" min={0} placeholder="Kill pts" value={e.kill_points} onChange={(x) => setEntry(i, 'kill_points', x.target.value)} />
                    </div>
                  ))}
                  <button className="btn-ghost" onClick={() => setForm({ ...form, entries: [...form.entries, emptyEntry()] })}>+ Team</button>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <TeamSelect value={form.team_a_id} onChange={(e) => setForm({ ...form, team_a_id: e.target.value })} />
                  <TeamSelect value={form.team_b_id} onChange={(e) => setForm({ ...form, team_b_id: e.target.value })} />
                  <input className="input" type="number" min={0} value={form.score_a} onChange={(e) => setForm({ ...form, score_a: e.target.value })} aria-label="Score A" />
                  <input className="input" type="number" min={0} value={form.score_b} onChange={(e) => setForm({ ...form, score_b: e.target.value })} aria-label="Score B" />
                </div>
              )}
              <Field label="Match screenshot (optional)"><input className="input" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => e.target.files[0] && upload(e.target.files[0]).catch((x) => toast(x.message, true))} /></Field>
              {published && <Field label="Correction reason (required)"><input className="input" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></Field>}
              <div className="flex gap-2"><button className="btn-primary" onClick={save}>Save match</button><button className="btn-ghost" onClick={() => setForm(null)}>Cancel</button></div>
            </div>
          )}

          <div>
            <div className="label">Revision history</div>
            {revs.data?.length ? revs.data.map((r) => <div key={r.revision} className="rounded-2xl bg-ops-raised p-2 text-xs">Rev {r.revision} · {new Date(r.created_at).toLocaleString()} · {r.reason || '—'}</div>) : <p className="text-xs text-ops-mute">No revisions yet.</p>}
          </div>
        </div>
      )}
    </Modal>
  )
}
