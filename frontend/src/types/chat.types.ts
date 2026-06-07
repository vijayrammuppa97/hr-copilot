export type FeedbackValue = 'helpful' | 'not_helpful'

export interface Message {
  id:                string
  role:              'user' | 'assistant'
  content:           string
  sources?:          string[]
  confidence?:       number
  followUpQuestions?: string[]
  timestamp:         string
  isError?:          boolean
  feedback?:         FeedbackValue | null
}

export interface ChatRequest {
  message:        string
  conversationId: string
  caseId?:        string
  userId?:        string
}

export interface FeedbackRequest {
  messageId:      string
  conversationId: string
  feedback:       FeedbackValue
}

export interface UserSession {
  session_id:    string
  started_at:    string
  updated_at:    string
  message_count: number
  preview:       string | null
}
