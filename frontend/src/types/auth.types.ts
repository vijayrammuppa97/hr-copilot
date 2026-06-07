export interface AuthUser {
  token:     string
  email:     string
  full_name: string
  user_id:   string
  role?:     string
}

export interface UserProfile {
  tenure_years?:    number | null
  employment_type?: string | null
  department?:      string | null
  role?:            string | null
}
