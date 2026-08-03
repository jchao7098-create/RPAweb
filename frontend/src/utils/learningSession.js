const TOKEN_KEY = 'learning_token'
const ROLE_KEY = 'learning_role'
const PROFILE_KEY = 'learning_profile'

export const getLearningToken = () => localStorage.getItem(TOKEN_KEY) || ''

export function setLearningSession({ token, role }) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
  if (role) localStorage.setItem(ROLE_KEY, role)
  else localStorage.removeItem(ROLE_KEY)
}

export function clearLearningSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ROLE_KEY)
  localStorage.removeItem(PROFILE_KEY)
}

export function getCachedLearningProfile() {
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null') }
  catch { return null }
}

export function setCachedLearningProfile(profile) {
  if (profile) localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
  else localStorage.removeItem(PROFILE_KEY)
}

export const canViewReport = (profile) => profile?.can_view_learning_report === true
export const canViewLearningStats = (profile) => profile?.can_view_learning_stats === true
export const canManageLearning = (profile) => profile?.can_manage_learning === true
