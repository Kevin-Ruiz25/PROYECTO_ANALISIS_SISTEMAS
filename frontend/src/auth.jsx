import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken } from './api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    if (!getToken()) return
    api.me()
      .then(setUser)
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  async function login(email, password) {
    const data = await api.login(email, password)
    localStorage.setItem('token', data.access_token)
    setUser(data.user)
  }

  function logout() {
    localStorage.removeItem('token')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}
