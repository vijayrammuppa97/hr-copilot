import { useState, useCallback, useEffect } from 'react'
import { signupApi, loginApi, logoutApi, verifyTokenApi } from '../api/auth.api'
import {
  AUTH_TOKEN_KEY, AUTH_EMAIL_KEY, AUTH_NAME_KEY,
  USER_ID_KEY, USERNAME_KEY, STORAGE_KEY, CONVERSATION_ID_KEY, AUTH_ROLE_KEY,
} from '../constants'
import type { AuthUser, UserProfile } from '../types'

interface UseAuthReturn {
  authUser:    AuthUser | null
  authChecked: boolean
  isAdmin:     boolean
  userProfile: UserProfile | null
  setUserProfile: (p: UserProfile | null) => void
  handleAuth:  (user: AuthUser) => void
  handleLogout: () => void
}

export function useAuth(): UseAuthReturn {
  const [authUser,     setAuthUser]     = useState<AuthUser | null>(null)
  const [authChecked,  setAuthChecked]  = useState(false)
  const [userProfile,  setUserProfile]  = useState<UserProfile | null>(null)

  // Verify stored token on mount
  useEffect(() => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) { setAuthChecked(true); return }

    verifyTokenApi(token)
      .then(data => {
        if (data) {
          setAuthUser(data)
          localStorage.setItem(AUTH_TOKEN_KEY, data.token)
          localStorage.setItem(AUTH_EMAIL_KEY, data.email)
          localStorage.setItem(AUTH_NAME_KEY,  data.full_name)
          localStorage.setItem(USER_ID_KEY,    data.user_id)
          localStorage.setItem(AUTH_ROLE_KEY,  data.role ?? 'user')
        } else {
          localStorage.removeItem(AUTH_TOKEN_KEY)
          localStorage.removeItem(AUTH_EMAIL_KEY)
          localStorage.removeItem(AUTH_NAME_KEY)
          localStorage.removeItem(AUTH_ROLE_KEY)
        }
      })
      .catch(() => {
        // Backend unreachable — restore from localStorage
        const email     = localStorage.getItem(AUTH_EMAIL_KEY) ?? ''
        const full_name = localStorage.getItem(AUTH_NAME_KEY)  ?? ''
        const user_id   = localStorage.getItem(USER_ID_KEY)    ?? ''
        const role      = localStorage.getItem(AUTH_ROLE_KEY)  ?? 'user'
        if (token && email) setAuthUser({ token, email, full_name, user_id, role })
      })
      .finally(() => setAuthChecked(true))
  }, [])

  const handleAuth = useCallback((user: AuthUser) => {
    localStorage.setItem(AUTH_TOKEN_KEY, user.token)
    localStorage.setItem(AUTH_EMAIL_KEY, user.email)
    localStorage.setItem(AUTH_NAME_KEY,  user.full_name)
    localStorage.setItem(USER_ID_KEY,    user.user_id)
    localStorage.setItem(AUTH_ROLE_KEY,  user.role ?? 'user')
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(CONVERSATION_ID_KEY)
    setAuthUser(user)
  }, [])

  const handleLogout = useCallback(() => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (token) logoutApi(token)
    ;[AUTH_TOKEN_KEY, AUTH_EMAIL_KEY, AUTH_NAME_KEY, AUTH_ROLE_KEY, USER_ID_KEY, USERNAME_KEY, STORAGE_KEY, CONVERSATION_ID_KEY]
      .forEach(k => localStorage.removeItem(k))
    setAuthUser(null)
    setUserProfile(null)
  }, [])

  const isAdmin = authUser?.role === 'admin'

  return { authUser, authChecked, isAdmin, userProfile, setUserProfile, handleAuth, handleLogout }
}

export { signupApi, loginApi }
