import { useState, useEffect, useCallback } from 'react'
import { registerUserApi, getUserSessionsApi } from '../api/users.api'
import { USER_ID_KEY, USERNAME_KEY } from '../constants'
import type { UserProfile, UserSession } from '../types'

interface UseUserProfileReturn {
  userId:       string
  username:     string
  userSessions: UserSession[]
  userProfile:  UserProfile | null
  setUserProfile: (p: UserProfile | null) => void
  clearUserState: () => void
}

export function useUserProfile(authUserId: string | undefined): UseUserProfileReturn {
  const [userId,       setUserId]       = useState<string>('')
  const [username,     setUsername]     = useState<string>('')
  const [userSessions, setUserSessions] = useState<UserSession[]>([])
  const [userProfile,  setUserProfile]  = useState<UserProfile | null>(null)

  useEffect(() => {
    if (!authUserId) return
    const storedId   = localStorage.getItem(USER_ID_KEY)  ?? ''
    const storedName = localStorage.getItem(USERNAME_KEY) ?? ''

    registerUserApi({ user_id: storedId || undefined, username: storedName || undefined })
      .then(data => {
        if (!data) return
        setUserId(data.user_id)
        setUsername(data.username)
        setUserProfile({
          tenure_years:    data.tenure_years,
          employment_type: data.employment_type,
          department:      data.department,
          role:            data.role,
        })
        localStorage.setItem(USER_ID_KEY,  data.user_id)
        localStorage.setItem(USERNAME_KEY, data.username)
        return getUserSessionsApi(data.user_id).then(setUserSessions)
      })
      .catch(() => {})
  }, [authUserId])

  const clearUserState = useCallback(() => {
    setUserId('')
    setUsername('')
    setUserSessions([])
    setUserProfile(null)
  }, [])

  return { userId, username, userSessions, userProfile, setUserProfile, clearUserState }
}
