import { useState } from 'react'
import { api, fmtDate } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Badge, ErrorBox, Field, Modal, Spinner, Table, useAction, useAsync, useToast } from '../../components/ui'
import RichTextEditor from '../../components/RichTextEditor'

const blank = () => ({ title: '', category: 'General', summary: '', content_html: '', image_path: null, pinned: false, featured: false, email_notify: false, target: { audience: 'everyone', divisions: [], cohort_ids: [] } })

export default function AnnouncementsAdmin() {
  const [status, setStatus] = useState('')
  const list = useAsync(() => api.get(`/api/admin/announcements${status ? `?status=${status}` : ''}`), [status])
  const cats = useAsync(() => api.get('/api/announcements/categories'))
  const cohorts = useAsync(() => api.get('/api/mythic/admin/cohorts').catch(() => []))
  const { hasRole } = useAuth()
  const [toast, node] = useToast()
  const act = useAction(list.reload, toast)
  const [form, setForm] = useState(null)
  const [when, setWhen] = useState('')
  const finance = hasRole('finance_admin')

  const edit = (a) => setForm({ id: a.id, title: a.title, category: a.category, summary: a.summary, content_html: a.content_html, image_path: null, pinned: a.pinned, featured: a.featured, email_notify: false, target: a.target || blank().target })
  const payload = () => ({ ...form, target: { audience: form.target.audience, divisions: form.target.divisions, cohort_ids: form.target.cohort_ids } })
  const save = async (publish) => {
    await act(async () => {
      let id = form.id
      if (id) { const { id: _i, ...patch } = payload(); await api.patch(`/api/admin/announcements/${id}`, patch) }
      else id = (await api.post('/api/admin/announcements', payload())).id
      if (publish === 'now') await api.post(`/api/admin/announcements/${id}/publish`, {})
      if (publish === 'schedule') await api.post(`/api/admin/announcements/${id}/publish`, { publish_at: new Date(when).toISOString() })
      setForm(null)
    }, publish ? 'Saved & publishing handled' : 'Draft saved')
  }
  const upload = async (file) => { const fd = new FormData(); fd.append('file', file); const r = await api.form('/api/admin/announcements/upload', fd); setForm((f) => ({ ...f, image_path: r.path })) }
  const setT = (k, v) => setForm({ ...form, target: { ...form.target, [k]: v } })

  return (
    <div className="space-y-6">
      {node}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Announcements</h1>
        <button className="btn-primary" onClick={() => setForm(blank())}>New announcement</button>
      </div>
      <select className="input max-w-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All</option>{['draft', 'scheduled', 'published', 'archived'].map((s) => <option key={s}>{s}</option>)}
      </select>
      {list.loading && <Spinner />}<ErrorBox message={list.error} />
      <Table head={['Title', 'Category', 'Audience', 'Status', 'Date', '']}>
        {list.data?.map((a) => (
          <tr key={a.id}>
            <td className="px-4 py-3 font-semibold">{a.pinned && 'Pinned: '}{a.title}</td><td className="px-4 py-3">{a.category}</td>
            <td className="px-4 py-3 text-xs">{a.target?.audience}</td>
            <td className="px-4 py-3"><Badge status={a.status}>{a.status}</Badge></td>
            <td className="px-4 py-3 text-xs">{fmtDate(a.publish_at || a.published_at)}</td>
            <td className="space-x-1 px-4 py-3">
              {a.status !== 'archived' && <button className="btn-ghost" onClick={() => edit(a)}>Edit</button>}
              {['draft', 'scheduled'].includes(a.status) && <button className="btn-primary" onClick={() => act(() => api.post(`/api/admin/announcements/${a.id}/publish`, {}), 'Published')}>Publish</button>}
              {a.status === 'published' && <button className="btn-ghost" onClick={() => act(() => api.post(`/api/admin/announcements/${a.id}/unpublish`), 'Unpublished')}>Unpublish</button>}
              {a.status !== 'archived' && <button className="btn-danger" onClick={() => act(() => api.post(`/api/admin/announcements/${a.id}/archive`), 'Archived')}>Archive</button>}
            </td>
          </tr>
        ))}
      </Table>

      {form && (
        <Modal title={form.id ? 'Edit announcement' : 'New announcement'} onClose={() => setForm(null)}>
          <div className="space-y-3">
            <Field label="Title"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Category"><select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{cats.data?.map((c) => <option key={c}>{c}</option>)}</select></Field>
              <Field label="Featured image"><input className="input" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => e.target.files[0] && upload(e.target.files[0]).catch((x) => toast(x.message, true))} /></Field>
            </div>
            <Field label="Short description (max 400)"><textarea className="input" rows={2} maxLength={400} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} /></Field>
            <div><span className="label">Content</span><RichTextEditor value={form.content_html} onChange={(v) => setForm((f) => ({ ...f, content_html: v }))} /></div>
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} /> Pin</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.featured} onChange={(e) => setForm({ ...form, featured: e.target.checked })} /> Featured</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.email_notify} onChange={(e) => setForm({ ...form, email_notify: e.target.checked })} /> Also email recipients</label>
            </div>
            <Field label="Audience">
              <select className="input" value={form.target.audience} onChange={(e) => setT('audience', e.target.value)}>
                <option value="everyone">Everyone</option><option value="verified">Verified OPS members</option><option value="divisions">Specific game divisions</option>
                {finance && <><option value="mythic">Mythic Circle members</option><option value="cohorts">Specific cohorts</option></>}
              </select>
            </Field>
            {!finance && <p className="text-xs text-ops-mute">Mythic Circle and cohort notices can only be sent by finance administrators.</p>}
            {form.target.audience === 'divisions' && <Field label="Divisions (comma separated)"><input className="input" value={form.target.divisions.join(', ')} onChange={(e) => setT('divisions', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} /></Field>}
            {form.target.audience === 'cohorts' && (
              <Field label="Cohorts"><select multiple className="input h-24" value={form.target.cohort_ids.map(String)} onChange={(e) => setT('cohort_ids', [...e.target.selectedOptions].map((o) => Number(o.value)))}>
                {cohorts.data?.map((c) => <option key={c.cohort_id} value={c.cohort_id}>{c.name}</option>)}</select></Field>
            )}
            <Field label="Schedule (optional)"><input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost" onClick={() => save(null)}>Save draft</button>
              <button className="btn-primary" onClick={() => save('now')}>Publish now</button>
              <button className="btn-ghost" disabled={!when} onClick={() => save('schedule')}>Schedule</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
