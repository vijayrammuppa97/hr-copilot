// Barrel exports — organised by domain
// Usage: import { ChatMessage, Sidebar, AuthPage } from './components'

// Auth
export { default as AuthPage } from './AuthPage'

// Chat
export { default as ChatMessage }    from './ChatMessage'
export { default as ChatInput }      from './ChatInput'
export { default as LoadingSkeleton } from './LoadingSkeleton'

// Layout
export { default as Sidebar }        from './Sidebar'
export { default as SessionHistory } from './SessionHistory'

// Onboarding
export { default as WorkflowProgress } from './WorkflowProgress'
export { default as EscalationModal }  from './EscalationModal'

// Admin
export { default as AdminDashboard } from './AdminDashboard'

// Common
export { default as ErrorBoundary } from './ErrorBoundary'
