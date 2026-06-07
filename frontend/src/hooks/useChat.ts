import { useState, useCallback } from 'react'
import { chatApi, uploadDocumentApi } from '../api/chat.api'
import { STORAGE_KEY, CONVERSATION_ID_KEY } from '../constants'
import { generateId, getOrCreateConversationId } from '../utils/helpers'
import type { Message } from '../types'

interface UseChatReturn {
  messages:          Message[]
  isLoading:         boolean
  error:             string | null
  lastFailedMessage: string | null
  isUploading:       boolean
  conversationId:    React.MutableRefObject<string>
  sendMessage:       (content: string, userId?: string, caseId?: string) => Promise<void>
  handleRetry:       () => void
  handleFileUpload:  (file: File) => Promise<{ name: string; sections: number } | null>
  clearChat:         () => void
  setMessages:       React.Dispatch<React.SetStateAction<Message[]>>
  setError:          (e: string | null) => void
}

function loadPersistedMessages(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Message[]) : []
  } catch { return [] }
}

export function useChat(): UseChatReturn {
  const [messages,          setMessages]          = useState<Message[]>(loadPersistedMessages)
  const [isLoading,         setIsLoading]         = useState(false)
  const [error,             setError]             = useState<string | null>(null)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const [isUploading,       setIsUploading]       = useState(false)
  const conversationId = { current: getOrCreateConversationId() } as React.MutableRefObject<string>

  const sendMessage = useCallback(async (content: string, userId?: string, caseId?: string) => {
    const trimmed = content.trim()
    if (!trimmed || isLoading) return

    const userMsg: Message = { id: generateId(), role: 'user', content: trimmed, timestamp: new Date().toISOString() }
    setMessages(prev => {
      const next = [...prev, userMsg]
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* quota */ }
      return next
    })
    setIsLoading(true)
    setError(null)
    setLastFailedMessage(null)

    const assistantId = generateId()

    try {
      const res = await chatApi({ message: trimmed, conversationId: conversationId.current, caseId, userId })
      if (!res.ok) {
        const j = await res.json().catch(() => ({})) as { detail?: string }
        throw new Error(j.detail ?? `Server error ${res.status}`)
      }

      const reader  = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body')

      setIsLoading(false)
      setMessages(prev => [...prev, {
        id: assistantId, role: 'assistant', content: '', sources: [], confidence: 0,
        timestamp: new Date().toISOString(), feedback: null,
      }])

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6)) as {
              type: string; text?: string; sources?: string[]
              confidence?: number; follow_up_questions?: string[]
              timestamp?: string; message?: string
            }
            if (evt.type === 'token' && evt.text) {
              setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: m.content + evt.text } : m))
            } else if (evt.type === 'done') {
              setMessages(prev => prev.map(m => m.id === assistantId ? {
                ...m,
                sources:           evt.sources ?? [],
                confidence:        evt.confidence ?? 0,
                followUpQuestions: evt.follow_up_questions ?? [],
                timestamp:         evt.timestamp ?? m.timestamp,
              } : m))
            } else if (evt.type === 'error') {
              throw new Error(evt.message ?? 'Stream error')
            }
          } catch { /* malformed frame */ }
        }
      }
    } catch (err) {
      const isTimeout = err instanceof DOMException && err.name === 'TimeoutError'
      const msg = isTimeout
        ? 'Request timed out. Ollama may still be loading the model — please try again.'
        : err instanceof Error ? err.message : 'Unexpected error.'
      setError(msg)
      setLastFailedMessage(trimmed)
      setMessages(prev => [...prev, {
        id: generateId(), role: 'assistant',
        content: `Unable to get a response: ${msg}\n\nUse the **Get Human Help** button for immediate assistance.`,
        timestamp: new Date().toISOString(), isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, conversationId])

  const handleRetry = useCallback(() => {
    if (!lastFailedMessage) return
    setMessages(prev => {
      const next = [...prev]
      if (next.at(-1)?.isError) next.pop()
      if (next.at(-1)?.role === 'user') next.pop()
      return next
    })
    setError(null)
    const msg = lastFailedMessage
    setLastFailedMessage(null)
    void sendMessage(msg)
  }, [lastFailedMessage, sendMessage])

  const handleFileUpload = useCallback(async (file: File) => {
    setIsUploading(true)
    try {
      const result = await uploadDocumentApi(file)
      if (!result) { setError('Upload failed — check file format and try again.'); return null }
      return { name: result.filename, sections: result.sections_added }
    } catch { setError('Upload failed. Is the backend running?'); return null }
    finally { setIsUploading(false) }
  }, [])

  const clearChat = useCallback(() => {
    setMessages([]); setError(null); setLastFailedMessage(null)
    const newId = generateId()
    conversationId.current = newId
    localStorage.setItem(CONVERSATION_ID_KEY, newId)
    localStorage.removeItem(STORAGE_KEY)
  }, [conversationId])

  return {
    messages, isLoading, error, lastFailedMessage, isUploading,
    conversationId, sendMessage, handleRetry, handleFileUpload, clearChat,
    setMessages, setError,
  }
}
