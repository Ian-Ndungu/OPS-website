import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, STAFF } from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setReady(true); return }
    try { setUser(await api.get('/api/auth/me')) } catch { setToken(null); setUser(null) }
    setReady(true)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const login = async (email, password) => { await api.login(email, password); await refresh() }
  const logout = () => { setToken(null); setUser(null) }
  const isStaff = !!user && STAFF.includes(user.role)
  const hasRole = (...roles) => !!user && (user.role === 'super_admin' || roles.includes(user.role))

  return <Ctx.Provider value={{ user, ready, login, logout, refresh, isStaff, hasRole }}>{children}</Ctx.Provider>
}
