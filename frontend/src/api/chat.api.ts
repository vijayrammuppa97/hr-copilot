import { API_BASE, CHAT_TIMEOUT_MS, UPLOAD_TIMEOUT_MS } from '../constants'

export interface ChatPayload {
  message:        string
  conversationId: string
  caseId?:        string
  userId?:        string
}

/** Opens an SSE stream to /api/chat. Returns the raw Response for the caller to read. */
export async function chatApi(payload: ChatPayload): Promise<Response> {
  return fetch(`${API_BASE}/api/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
    signal:  AbortSignal.timeout(CHAT_TIMEOUT_MS),
  })
}

export async function feedbackApi(
  messageId: string, conversationId: string, feedback: 'helpful' | 'not_helpful'
): Promise<void> {
  await fetch(`${API_BASE}/api/feedback`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ messageId, conversationId, feedback }),
  }).catch(() => {})
}

export async function uploadDocumentApi(
  file: File
): Promise<{ filename: string; sections_added: number } | null> {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body:   formData,
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
    })
    return res.ok ? (await res.json()) : null
  } catch {
    return null
  }
}
