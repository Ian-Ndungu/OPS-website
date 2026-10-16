const TOKEN_KEY = 'ops_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(method, path, body, isForm = false) {
  const headers = {}
  const t = getToken()
  if (t) headers.Authorization = `Bearer ${t}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined })
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data?.detail
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail || `Request failed (${res.status})`
    throw new ApiError(msg, res.status)
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b = {}) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  patch: (p, b) => request('PATCH', p, b),
  form: (p, fd) => request('POST', p, fd, true),
  async login(email, password) {
    const body = new URLSearchParams({ username: email, password })
    const res = await fetch('/api/auth/login', { method: 'POST', body })
    const data = await res.json()
    if (!res.ok) throw new ApiError(data.detail || 'Login failed', res.status)
    setToken(data.access_token)
  },
}

export const kes = (n) => `KSh ${Number(n || 0).toLocaleString('en-KE')}`
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const label = (s) => String(s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const STAFF = ['content_admin', 'results_admin', 'clan_verifier', 'finance_admin', 'super_admin']
