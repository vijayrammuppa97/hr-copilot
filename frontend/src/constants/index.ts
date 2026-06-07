// ── localStorage keys ─────────────────────────────────────────────────────── //
export const STORAGE_KEY         = 'hr_copilot_messages'
export const CONVERSATION_ID_KEY = 'hr_copilot_conversation_id'
export const CASE_ID_KEY         = 'hr_copilot_case_id'
export const USER_ID_KEY         = 'hr_copilot_user_id'
export const USERNAME_KEY        = 'hr_copilot_username'
export const AUTH_TOKEN_KEY      = 'hr_copilot_auth_token'
export const AUTH_EMAIL_KEY      = 'hr_copilot_auth_email'
export const AUTH_NAME_KEY       = 'hr_copilot_auth_name'
export const AUTH_ROLE_KEY       = 'hr_copilot_auth_role'

// ── API ───────────────────────────────────────────────────────────────────── //
export const API_BASE            = import.meta.env.VITE_API_URL ?? ''
export const ALLOWED_DOMAIN      = 'acme.com'

// ── Chat limits ───────────────────────────────────────────────────────────── //
export const MAX_HISTORY_ENTRIES  = 12
export const CHAT_TIMEOUT_MS      = 125_000
export const UPLOAD_TIMEOUT_MS    = 30_000
