import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { api, fmtDate } from '../lib/api'
import { useAuth } from '../lib/auth'

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/mythic-circle', label: 'Mythic Circle' },
  { to: '/results', label: 'Results' },
  { to: '/announcements', label: 'Announcements' },
]

function currentTheme() {
  const set = document.documentElement.dataset.theme
  if (set) return set
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme)
  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('ops_theme', next) } catch { /* storage unavailable */ }
    setTheme(next)
  }
  return (
    <button className="btn-ghost !px-3" onClick={flip} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title="Switch theme">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        {theme === 'dark'
          ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>
          : <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />}
      </svg>
    </button>
  )
}

function Bell() {
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const load = () => api.get('/api/notifications').then(setItems).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t) }, [])
  const unread = items.filter((n) => !n.read).length
  const read = async (n) => { await api.post(`/api/notifications/${n.id}/read`).catch(() => {}); load() }
  return (
    <div className="relative">
      <button className="btn-ghost relative !px-3" onClick={() => setOpen(!open)} aria-label={`Notifications, ${unread} unread`} aria-expanded={open}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>
        {unread > 0 && <span className="num absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-ops-accent px-1 text-xs font-bold text-ops-on-accent">{unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-3 max-h-96 w-80 overflow-y-auto rounded-3xl bg-ops-card p-2 shadow-2xl ring-1 ring-ops-line">
          {items.length === 0 && <div className="p-4 text-sm text-ops-mute">You're all caught up.</div>}
          {items.map((n) => (
            <Link key={n.id} to={n.link || '#'} onClick={() => { read(n); setOpen(false) }}
              className={`block rounded-2xl p-3 text-sm hover:bg-ops-raised ${n.read ? 'opacity-60' : ''}`}>
              <div className="font-semibold text-white">{n.title}</div>
              {n.body && <div className="text-xs text-ops-mute">{n.body}</div>}
              <div className="mt-1 text-xs text-ops-mute">{fmtDate(n.created_at)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

const linkCls = ({ isActive }) => `rounded-full px-4 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-ops-raised text-white' : 'text-ops-mute hover:text-white'}`

export function SiteLayout() {
  const { user, logout, isStaff } = useAuth()
  const nav = useNavigate()
  const [menu, setMenu] = useState(false)
  return (
    <div className="min-h-screen">
      <header className="sticky top-3 z-30 mx-auto mt-3 max-w-6xl px-3">
        <div className="flex items-center justify-between gap-2 rounded-full bg-ops-card/80 py-2 pl-5 pr-2 shadow-lg shadow-black/10 ring-1 ring-ops-line/70 backdrop-blur-xl">
          <Link to="/" className="flex items-center gap-2 font-display text-xl font-extrabold tracking-tight text-white">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="rgb(var(--accent))" strokeWidth="3.4" strokeDasharray="9 3.2" strokeLinecap="round" /></svg>
            OPS
          </Link>
          <nav className="hidden items-center md:flex" aria-label="Main">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.end} className={linkCls}>{n.label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            {user ? (
              <>
                <Bell />
                <Link className="btn-primary hidden sm:inline-flex" to="/dashboard/mythic-circle">My circle</Link>
                {isStaff && <Link className="btn-ghost hidden lg:inline-flex" to="/admin/mythic-circle">Admin</Link>}
                <button className="btn-ghost hidden lg:inline-flex" onClick={() => { logout(); nav('/') }}>Log out</button>
              </>
            ) : (
              <><Link className="btn-ghost hidden sm:inline-flex" to="/login">Log in</Link><Link className="btn-primary" to="/register">Join OPS</Link></>
            )}
            <button className="btn-ghost !px-3 md:hidden" onClick={() => setMenu(!menu)} aria-label="Menu" aria-expanded={menu}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
            </button>
          </div>
        </div>
        {menu && (
          <div className="mt-2 space-y-1 rounded-3xl bg-ops-card p-3 shadow-xl ring-1 ring-ops-line md:hidden" onClick={() => setMenu(false)}>
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.end} className={linkCls}>{n.label}</NavLink>)}
            {user ? (<>
              <Link className="block rounded-full px-4 py-2 text-sm font-medium" to="/dashboard/mythic-circle">My circle</Link>
              {isStaff && <Link className="block rounded-full px-4 py-2 text-sm font-medium" to="/admin/mythic-circle">Admin</Link>}
              <button className="block rounded-full px-4 py-2 text-sm font-medium" onClick={() => { logout(); nav('/') }}>Log out</button>
            </>) : <Link className="block rounded-full px-4 py-2 text-sm font-medium" to="/login">Log in</Link>}
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6"><Outlet /></main>
      <footer className="mx-auto max-w-6xl px-6 pb-10 text-sm text-ops-mute">OPS Esports. Official results and member services.</footer>
    </div>
  )
}

export const ADMIN_NAV = [
  { to: '/admin/mythic-circle', label: 'Mythic Circle', end: true, roles: ['finance_admin', 'clan_verifier'] },
  { to: '/admin/mythic-circle/verification', label: 'Clan Verification', roles: ['clan_verifier'] },
  { to: '/admin/mythic-circle/cohorts', label: 'Cohorts', roles: ['finance_admin'] },
  { to: '/admin/mythic-circle/contributions', label: 'Contributions', roles: ['finance_admin'] },
  { to: '/admin/mythic-circle/payouts', label: 'Payouts', roles: ['finance_admin'] },
  { to: '/admin/results', label: 'Tournament Results', roles: ['content_admin', 'results_admin'] },
  { to: '/admin/announcements', label: 'Announcements', roles: ['content_admin', 'finance_admin'] },
]

export function AdminLayout() {
  const { user, ready, isStaff, hasRole, logout } = useAuth()
  const nav = useNavigate()
  if (!ready) return null
  if (!user) return <Navigate to="/login" replace />
  if (!isStaff) return <Navigate to="/" replace />
  const items = ADMIN_NAV.filter((i) => hasRole(...i.roles))
  return (
    <div className="min-h-screen gap-4 p-3 md:flex">
      <aside className="mb-3 rounded-[28px] bg-ops-card p-3 md:sticky md:top-3 md:mb-0 md:h-[calc(100vh-1.5rem)] md:w-64 md:shrink-0 md:overflow-y-auto">
        <div className="flex items-center justify-between px-2 py-2">
          <Link to="/" className="flex items-center gap-2 font-display text-xl font-extrabold text-white">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="rgb(var(--accent))" strokeWidth="3.4" strokeDasharray="9 3.2" strokeLinecap="round" /></svg>
            OPS Admin
          </Link>
          <ThemeToggle />
        </div>
        <nav className="mt-2 flex gap-1 overflow-x-auto md:block md:space-y-1" aria-label="Admin">
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.end}
              className={({ isActive }) => `block whitespace-nowrap rounded-2xl px-4 py-2.5 text-sm font-medium transition-colors ${isActive ? 'bg-ops-accent text-ops-on-accent' : 'text-slate-300 hover:bg-ops-raised'}`}>{i.label}</NavLink>
          ))}
        </nav>
        <div className="mt-4 hidden border-t border-ops-line/60 px-2 pt-4 text-sm md:block">
          <div className="font-semibold text-white">{user.gamer_tag}</div>
          <div className="text-ops-mute">{user.role.replace('_', ' ')}</div>
          <button className="mt-3 text-ops-link underline underline-offset-2" onClick={() => { logout(); nav('/') }}>Log out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-1 py-2 md:px-6 md:py-6"><Outlet /></main>
    </div>
  )
}

export function RequireAuth({ children }) {
  const { user, ready } = useAuth()
  if (!ready) return null
  return user ? children : <Navigate to="/login" replace />
}
