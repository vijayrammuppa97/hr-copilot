export type FeedbackValue = 'helpful' | 'not_helpful'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  confidence?: number
  timestamp: string
  isError?: boolean
  feedback?: FeedbackValue | null
}

export interface ChatRequest {
  message: string
  conversationId: string
}

export interface ChatResponse {
  message: string
  sources: string[]
  confidence: number
  timestamp: string
}

export interface FeedbackRequest {
  messageId: string
  conversationId: string
  feedback: FeedbackValue
}

export interface SuggestedPrompt {
  label: string
  query: string
}
