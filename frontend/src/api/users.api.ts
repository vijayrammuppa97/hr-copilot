import { API_BASE } from '../constants'
import type { UserSession, UserProfile } from '../types'

interface RegisterPayload {
  user_id?:        string
  username?:       string
  tenure_years?:   number | null
  employment_type?: string | null
  department?:     string | null
  role?:           string | null
}

interface UserRecord extends UserProfile {
  user_id:   string
  username:  string
  created_at: string
  last_seen:  string
}

export async function registerUserApi(payload: RegisterPayload): Promise<UserRecord | null> {
  try {
    const res = await fetch(`${API_BASE}/api/users/register`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    })
    return res.ok ? (await res.json() as UserRecord) : null
  } catch {
    return null
  }
}

export async function getUserSessionsApi(userId: string): Promise<UserSession[]> {
  try {
    const res = await fetch(`${API_BASE}/api/users/${userId}/sessions`)
    return res.ok ? (await res.json() as UserSession[]) : []
  } catch {
    return []
  }
}

export async function patchUserProfileApi(
  userId: string, profile: UserProfile
): Promise<UserRecord | null> {
  try {
    const res = await fetch(`${API_BASE}/api/users/${userId}/profile`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(profile),
    })
    return res.ok ? (await res.json() as UserRecord) : null
  } catch {
    return null
  }
}
