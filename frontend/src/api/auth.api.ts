import { API_BASE } from '../constants'
import type { AuthUser } from '../types'

export async function signupApi(
  email: string, password: string, fullName: string
): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ email, password, full_name: fullName }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? 'Signup failed')
  return data as AuthUser
}

export async function loginApi(
  email: string, password: string
): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ email, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? 'Login failed')
  return data as AuthUser
}

export async function logoutApi(token: string): Promise<void> {
  await fetch(`${API_BASE}/api/auth/logout`, {
    method:  'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => {})
}

export async function verifyTokenApi(token: string): Promise<AuthUser | null> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return res.ok ? (await res.json() as AuthUser) : null
  } catch {
    return null
  }
}
