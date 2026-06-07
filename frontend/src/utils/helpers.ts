import { CONVERSATION_ID_KEY } from '../constants'

export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
}

export function getOrCreateConversationId(): string {
  let id = localStorage.getItem(CONVERSATION_ID_KEY)
  if (!id) { id = generateId(); localStorage.setItem(CONVERSATION_ID_KEY, id) }
  return id
}

export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function getInitials(name: string): string {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
