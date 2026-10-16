import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmtDate, kes } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, Empty, ErrorBox, Field, Spinner, useAsync } from '../components/ui'
import { Podium, Standings, TeamLogo } from '../components/Leaderboard'
import SeatRing from '../components/SeatRing'

const CAT_TONE = { 'Important Notices': 'tone-bad', Maintenance: 'tone-warn', 'Tournament Updates': 'tone-info', 'Mythic Circle': 'tone-ok' }
const CategoryChip = ({ c }) => <span className={`badge ${CAT_TONE[c] || 'tone-mute'}`}>{c}</span>

export function AnnouncementCard({ a, lead = false }) {
  return (
    <Link to={`/announcements/${a.slug}`}
      className={`group block overflow-hidden rounded-[28px] bg-ops-card transition-colors hover:bg-ops-raised ${lead && a.image ? 'md:grid md:grid-cols-5' : ''}`}>
      {a.image && <img src={a.image} alt="" className={`w-full bg-ops-raised object-contain ${lead ? 'h-56 md:col-span-2 md:h-full md:max-h-96' : 'h-44'}`} />}
      <div className={`p-6 ${lead && a.image ? 'md:col-span-3' : ''}`}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <CategoryChip c={a.category} />
          {a.pinned && <span className="badge tone-warn">Pinned</span>}
        </div>
        <h3 className={`font-display font-bold leading-tight text-white ${lead ? 'text-3xl' : 'text-xl'}`}>{a.title}</h3>
        <p className={`mt-2 text-slate-400 ${lead ? 'text-base' : 'line-clamp-2 text-sm'}`}>{a.summary}</p>
        <div className="mt-4 text-sm text-ops-mute">{fmtDate(a.published_at)}{a.author ? ` by ${a.author}` : ''}</div>
      </div>
    </Link>
  )
}

function LatestResult({ t }) {
  if (!t) return <div className="rounded-[32px] bg-ops-card p-5 sm:p-8 text-ops-mute">No results have been published yet. They appear here as soon as an admin publishes them.</div>
  return (
    <Link to={`/results/${t.id}`} className="block rounded-[32px] bg-ops-card p-6 transition-colors hover:bg-ops-raised sm:p-8">
      <div className="flex items-center justify-between gap-3">
        <span className="badge tone-ok">Latest official result</span>
        <span className="text-sm text-ops-mute">{fmtDate(t.starts_on)}</span>
      </div>
      <h2 className="mt-4 font-display text-3xl font-bold leading-tight text-white">{t.name}</h2>
      <p className="text-sm text-ops-mute">{t.game}{t.game_mode ? `, ${t.game_mode}` : ''}</p>
      <ol className="mt-5 space-y-2">
        {t.podium.map((p) => (
          <li key={p.team_id} className={`flex items-center gap-4 rounded-2xl px-4 py-3 ${p.rank === 1 ? 'bg-ops-accent text-ops-on-accent' : 'bg-ops-raised'}`}>
            <span className="num w-6 font-display text-2xl font-extrabold">{p.rank}</span>
            <TeamLogo team={p} size="h-9 w-9" />
            <span className="min-w-0 flex-1 truncate font-semibold">{p.team}</span>
            <span className="num font-display text-lg font-bold">{p.total_points}<span className="ml-1 text-xs font-medium opacity-70">pts</span></span>
          </li>
        ))}
      </ol>
      <div className="mt-5 text-sm font-semibold text-ops-link">See full standings and every match</div>
    </Link>
  )
}

export function Home() {
  const news = useAsync(() => api.get('/api/announcements/latest?limit=4'))
  const results = useAsync(() => api.get('/api/results'))
  const plans = useAsync(() => api.get('/api/mythic/plans'))
  const plan = plans.data?.plans?.[0]
  const [lead, ...rest] = news.data || []
  return (
    <div className="space-y-16">
      <section className="grid items-center gap-10 pt-4 lg:grid-cols-[1.15fr_.85fr]">
        <div>
          <h1 className="max-w-[16ch] text-balance font-display text-4xl font-extrabold leading-[0.98] text-white sm:text-6xl lg:text-7xl">
            Play together. Rise together.
          </h1>
          <p className="mt-6 max-w-[52ch] text-lg leading-relaxed text-slate-300">
            Your home for OPSKe tournament results, clan news, and shared goals. Follow the action and build your savings with Mythic Circle, our fixed-term savings program for verified clan members.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/results" className="btn-primary !px-6 !py-3 text-base">See latest results</Link>
            <Link to="/mythic-circle" className="btn-ghost !px-6 !py-3 text-base">How Mythic Circle works</Link>
          </div>
        </div>
        {results.loading ? <Spinner /> : <LatestResult t={results.data?.[0]} />}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-[32px] bg-ops-card p-6 sm:p-8">
          <h2 className="font-display text-2xl font-bold text-white">Mythic Circle</h2>
          {plan ? (
            <>
              <div className="my-4"><SeatRing seats={plan.members} filled={plan.members - Math.min(plan.available_slots, plan.members)} open={Math.min(plan.available_slots, plan.members)} size={210}>
                <div className="num font-display text-3xl sm:text-5xl font-extrabold text-white">{Math.min(plan.available_slots, plan.members)}</div>
                <div className="text-sm text-ops-mute">seats open</div>
              </SeatRing></div>
              <p className="text-sm text-slate-300">{plan.members} players put in {kes(plan.monthly_kes)} a month for {plan.months} months. Everyone is paid {kes(plan.expected_payout_kes)} together at the end.</p>
              <Link to="/mythic-circle" className="btn-primary mt-5">Explore the circle</Link>
            </>
          ) : <Spinner />}
        </div>
        <div className="space-y-4 lg:col-span-2">
          <div className="flex items-end justify-between">
            <h2 className="font-display text-2xl font-bold text-white">Latest from the clan</h2>
            <Link to="/announcements" className="text-sm font-semibold text-ops-link">All announcements</Link>
          </div>
          <ErrorBox message={news.error} />
          {news.loading && <Spinner />}
          {news.data && !news.data.length && <Empty>No announcements yet. New posts from admins appear here.</Empty>}
          {lead && <AnnouncementCard a={lead} lead />}
          {rest.length > 0 && (
            <ul className="divide-y divide-ops-line/60 rounded-[28px] bg-ops-card px-6">
              {rest.map((a) => (
                <li key={a.id}>
                  <Link to={`/announcements/${a.slug}`} className="flex items-center justify-between gap-4 py-4">
                    <div className="min-w-0"><div className="truncate font-semibold text-white">{a.title}</div><div className="text-sm text-ops-mute">{a.category}, {fmtDate(a.published_at)}</div></div>
                    <span className="text-ops-link" aria-hidden="true">&rsaquo;</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

export function Login({ register = false }) {
  const { login } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ email: '', password: '', gamer_tag: '' })
  const [pending, setPending] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true)
    try {
      if (register) {
        await api.post('/api/auth/register', f)
        setPending(true)
        return
      } else await login(f.email, f.password)
      nav('/')
    } catch (x) { setErr(x.message) }
    finally { setBusy(false) }
  }
  if (pending && register) return <div role="status" className="tile mx-auto max-w-md space-y-4"><h1 className="font-display text-3xl font-bold">Account pending approval</h1><p>Your account has been created. An admin must approve it before you can log in.</p><Link className="btn-ghost" to="/login">Go to login</Link></div>
  return (
    <form onSubmit={submit} className="mx-auto mt-6 max-w-md space-y-5 rounded-[32px] bg-ops-card p-5 sm:p-8">
      <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-white">{register ? 'Join OPS' : 'Welcome back'}</h1>
      <ErrorBox message={err} />
      {register && <Field label="Gamer tag"><input className="input" required value={f.gamer_tag} onChange={set('gamer_tag')} autoComplete="nickname" /></Field>}
      <Field label="Email"><input className="input" type="email" required value={f.email} onChange={set('email')} autoComplete="email" /></Field>
      <Field label="Password"><input className="input" type="password" required minLength={8} value={f.password} onChange={set('password')} autoComplete={register ? 'new-password' : 'current-password'} /></Field>
      <button disabled={busy} className="btn-primary w-full !py-3">{register ? 'Create account' : 'Log in'}</button>
      <p className="text-center text-sm text-ops-mute">{register ? <Link className="link" to="/login">Have an account? Log in</Link> : <Link className="link" to="/register">New to OPS? Create an account</Link>}</p>
    </form>
  )
}

/* ------------------------------------------------------------ Results */
export function Results() {
  const [f, setF] = useState({ game: '', mode: '', tournament_id: '', date_from: '', date_to: '', status: '' })
  const filters = useAsync(() => api.get('/api/results-filters'))
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString()
  const { data, loading, error } = useAsync(() => api.get(`/api/results?${qs}`), [qs])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Tournament results</h1>
        <p className="mt-2 max-w-[60ch] text-slate-300">Only results published by OPS admins appear here. Corrections are tracked, and standings are recalculated from the published matches.</p>
      </div>
      <div className="grid gap-3 rounded-[28px] bg-ops-card p-4 sm:grid-cols-2 lg:grid-cols-6">
        <select className="input" value={f.game} onChange={set('game')} aria-label="Game"><option value="">All games</option>{filters.data?.games.map((g) => <option key={g}>{g}</option>)}</select>
        <select className="input" value={f.mode} onChange={set('mode')} aria-label="Mode"><option value="">All modes</option><option value="battle_royale">Battle Royale</option><option value="multiplayer">Multiplayer</option></select>
        <select className="input" value={f.tournament_id} onChange={set('tournament_id')} aria-label="Tournament"><option value="">All tournaments</option>{filters.data?.tournaments.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        <input className="input" type="date" value={f.date_from} onChange={set('date_from')} aria-label="From date" />
        <input className="input" type="date" value={f.date_to} onChange={set('date_to')} aria-label="To date" />
        <select className="input" value={f.status} onChange={set('status')} aria-label="Status"><option value="">All statuses</option><option value="completed">Completed</option><option value="upcoming">Upcoming</option></select>
      </div>
      {loading && <Spinner />}<ErrorBox message={error} />
      {data && !data.length && <Empty>No published results match these filters. Try clearing one.</Empty>}
      <div className="grid gap-5 lg:grid-cols-2">
        {data?.map((t) => (
          <Link key={t.id} to={`/results/${t.id}`} className="block rounded-[32px] bg-ops-card p-6 transition-colors hover:bg-ops-raised sm:p-7">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge status={t.event_status}>{t.event_status}</Badge>
              <span className="badge tone-mute">{t.mode === 'battle_royale' ? 'Battle Royale' : 'Multiplayer'}</span>
            </div>
            <h2 className="mt-3 font-display text-3xl font-bold leading-tight text-white">{t.name}</h2>
            <p className="mb-6 text-sm text-ops-mute">{t.game}{t.game_mode ? `, ${t.game_mode}` : ''}. {fmtDate(t.starts_on)}. {t.team_count} teams.</p>
            <Podium top={t.podium} />
            {t.mvp_player && <div className="mt-5 text-sm text-ops-mute">MVP <span className="font-semibold text-ops-link">{t.mvp_player}</span></div>}
          </Link>
        ))}
      </div>
    </div>
  )
}

export function ResultDetail() {
  const { id } = useParams()
  const { data: t, loading, error } = useAsync(() => api.get(`/api/results/${id}`), [id])
  if (loading) return <Spinner />
  if (error) return <ErrorBox message={error} />
  const br = t.mode === 'battle_royale'
  return (
    <div className="space-y-10">
      <div>
        <Link to="/results" className="text-sm font-semibold text-ops-link">All results</Link>
        <h1 className="mt-3 font-display text-3xl sm:text-5xl font-extrabold leading-tight text-white">{t.name}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-ops-mute">
          <Badge status={t.event_status}>{t.event_status}</Badge>
          <span>{t.game}{t.game_mode ? `, ${t.game_mode}` : ''}. {fmtDate(t.starts_on)}.</span>
          {t.mvp_player && <span>MVP <span className="font-semibold text-ops-link">{t.mvp_player}</span></span>}
        </div>
      </div>
      <div className="rounded-[32px] bg-ops-card p-6 sm:p-8"><Podium top={t.standings.slice(0, 3)} /></div>
      <section><h2 className="mb-4 font-display text-3xl font-bold text-white">Overall standings</h2><Standings rows={t.standings} mode={t.mode} /></section>
      <section className="space-y-4">
        <h2 className="font-display text-3xl font-bold text-white">Match by match</h2>
        {t.matches.map((m) => (
          <div key={m.match_no} className="rounded-[28px] bg-ops-card p-6">
            <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1">
              <h3 className="font-display text-2xl font-bold text-white">Match {m.match_no}</h3>
              {m.game_mode && <span className="badge tone-mute">{m.game_mode}</span>}
              <span className="text-sm text-ops-mute">Winner <span className="font-semibold text-white">{m.winner}</span></span>
              {m.mvp_player && <span className="text-sm text-ops-mute">MVP <span className="font-semibold text-ops-link">{m.mvp_player}</span></span>}
            </div>
            {br ? (
              <div className="overflow-x-auto"><table className="w-full min-w-[440px] text-sm">
                <thead className="text-left text-ops-mute"><tr><th className="py-2 font-medium">Place</th><th className="font-medium">Team</th><th className="font-medium">Kills</th><th className="font-medium">Placement pts</th><th className="font-medium">Kill pts</th><th className="font-medium">Total</th></tr></thead>
                <tbody>{m.entries.map((e) => <tr key={e.team_id} className="border-t border-ops-line/60"><td className="num py-2.5 font-display text-lg font-bold">{e.placement}</td><td className="font-medium text-white">{e.team}</td><td className="num">{e.kills}</td><td className="num">{e.placement_points}</td><td className="num">{e.kill_points}</td><td className="num font-bold text-ops-link">{e.total}</td></tr>)}</tbody>
              </table></div>
            ) : (
              <div className="flex flex-wrap items-center justify-center gap-4 py-2 sm:gap-8">
                <span className={`font-display text-2xl font-bold ${m.winner === m.team_a ? 'text-white' : 'text-ops-mute'}`}>{m.team_a}</span>
                <span className="num rounded-full bg-ops-accent px-6 py-2 font-display text-3xl font-extrabold text-ops-on-accent">{m.score_a} : {m.score_b}</span>
                <span className={`font-display text-2xl font-bold ${m.winner === m.team_b ? 'text-white' : 'text-ops-mute'}`}>{m.team_b}</span>
              </div>
            )}
            {m.screenshot && <a href={`/uploads/${m.screenshot}`} target="_blank" rel="noreferrer" className="link mt-3 inline-block text-sm">View match screenshot</a>}
          </div>
        ))}
      </section>
    </div>
  )
}

/* ------------------------------------------------------ Announcements */
export function Announcements() {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const cats = useAsync(() => api.get('/api/announcements/categories'))
  const { data, loading, error } = useAsync(
    () => api.get(`/api/announcements?${new URLSearchParams({ ...(q && { q }), ...(cat && { category: cat }) })}`), [q, cat])
  const lead = data?.find((a) => a.pinned) || data?.find((a) => a.featured) || data?.[0]
  const rest = data?.filter((a) => a !== lead) || []
  return (
    <div className="space-y-8">
      <h1 className="font-display text-3xl sm:text-5xl font-extrabold text-white">Announcements</h1>
      <div className="space-y-4">
        <input className="input max-w-md !rounded-full !px-5" placeholder="Search announcements" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search announcements" />
        <div className="flex flex-wrap gap-2" role="group" aria-label="Category">
          {['', ...(cats.data || [])].map((c) => (
            <button key={c} onClick={() => setCat(c)} aria-pressed={cat === c}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${cat === c ? 'bg-ops-accent text-ops-on-accent' : 'bg-ops-card text-slate-300 hover:bg-ops-raised'}`}>{c || 'All'}</button>
          ))}
        </div>
      </div>
      {loading && <Spinner />}<ErrorBox message={error} />
      {data && !data.length && <Empty>No announcements match. Try another category or search.</Empty>}
      {lead && <AnnouncementCard a={lead} lead />}
      {rest.length > 0 && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{rest.map((a) => <AnnouncementCard key={a.id} a={a} />)}</div>}
    </div>
  )
}

export function AnnouncementDetail() {
  const { slug } = useParams()
  const { data: a, loading, error } = useAsync(() => api.get(`/api/announcements/${slug}`), [slug])
  if (loading) return <Spinner />
  if (error) return <ErrorBox message={error} />
  return (
    <article className="mx-auto max-w-3xl">
      <Link to="/announcements" className="text-sm font-semibold text-ops-link">All announcements</Link>
      {a.image && <img src={a.image} alt="" className="mt-5 h-auto w-full rounded-[28px] bg-ops-raised object-contain" />}
      <div className="mt-6 flex flex-wrap gap-2"><CategoryChip c={a.category} />{a.pinned && <span className="badge tone-warn">Pinned</span>}</div>
      <h1 className="mt-3 font-display text-3xl sm:text-5xl font-extrabold leading-tight text-white">{a.title}</h1>
      <p className="mt-2 text-sm text-ops-mute">{fmtDate(a.published_at)}{a.author ? ` by ${a.author}` : ''}</p>
      {/* Server-sanitised HTML (bleach allow-list) */}
      <div className="prose-ops mt-6" dangerouslySetInnerHTML={{ __html: a.content_html }} />
    </article>
  )
}
