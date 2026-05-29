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
  caseId?: string
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

// ── Onboarding types ────────────────────────────────────────────────────── //

export type WorkflowItemStatus = 'pending' | 'completed' | 'skipped'
export type StageStatus = 'pending' | 'in_progress' | 'completed'
export type CaseStatus = 'active' | 'completed' | 'escalated' | 'on_hold'

export interface WorkflowItem {
  id: string
  label: string
  description: string
  status: WorkflowItemStatus
  completed_at?: string | null
}

export interface WorkflowStage {
  stage_id: string
  name: string
  icon: string
  description: string
  total_items: number
  completed_items: number
  status: StageStatus
  items: WorkflowItem[]
}

export interface Escalation {
  id: number
  reason: string
  status: 'open' | 'assigned' | 'resolved'
  escalated_by: string
  created_at: string
  resolved_at?: string | null
}

export interface OnboardingCase {
  case_id: string
  employee_name: string
  employee_email: string
  employee_id: string
  department: string
  role: string
  manager_name: string
  start_date: string
  current_stage: string
  status: CaseStatus
  created_at: string
  updated_at: string
  workflow: WorkflowStage[]
  escalations: Escalation[]
}

export interface CreateCaseRequest {
  employee_name: string
  employee_email: string
  employee_id?: string
  department?: string
  role?: string
  manager_name?: string
  start_date?: string
}
