import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, setUnauthorizedHandler } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined) // undefined = loading, null = signed out

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    api('auth/me').then(setUser).catch(() => setUser(null))
  }, [])

  const login = useCallback(async (login, password) => {
    const u = await api('auth/login', { method: 'POST', body: { login, password } })
    setUser(u)
    return u
  }, [])

  const logout = useCallback(async () => {
    try { await api('auth/logout', { method: 'POST' }) } finally { setUser(null) }
  }, [])

  return <AuthCtx.Provider value={{ user, setUser, login, logout }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)
