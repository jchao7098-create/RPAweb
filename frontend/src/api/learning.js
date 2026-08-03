import http from './http'
import { setCachedLearningProfile } from '@/utils/learningSession'

const data = (request) => request.then((response) => response.data)

export const fetchLearningMe = () => data(http.get('/learning/me'))
export async function loadLearningProfile() {
  const profile = await fetchLearningMe()
  setCachedLearningProfile(profile)
  return profile
}
export const fetchCurrentReport = () => data(http.get('/learning/reports/current'))
export const saveCurrentDraft = (payload) => data(http.put('/learning/reports/current/draft', payload))
export const submitCurrentReport = (payload) => data(http.post('/learning/reports/current/submit', payload))
export const fetchReportHistory = (params = {}) => data(http.get('/learning/reports/history', { params }))
export const fetchSubmissionHistory = () => data(http.get('/learning/reports/submission-history'))
export const fetchReport = (reportId) => data(http.get(`/learning/reports/${reportId}`))
export const saveReturnedDraft = (reportId, payload) => data(http.put(`/learning/reports/${reportId}/draft`, payload))
export const submitReturnedReport = (reportId, payload) => data(http.post(`/learning/reports/${reportId}/submit`, payload))
export const fetchWeeklyStats = (params = {}) => data(http.get('/learning/admin/weekly-stats', { params }))
export const fetchUserTrend = (userId, params = {}) => data(http.get(`/learning/admin/users/${userId}/trend`, { params }))
export const fetchUserLearningHistory = (userId) => data(http.get(`/learning/admin/users/${userId}/history`))
export const returnLearningReport = (reportId, payload) => data(http.post(`/learning/admin/reports/${reportId}/return`, payload))
export const fetchLearningUsers = (params = {}) => data(http.get('/learning/admin/users', { params }))
export const changeLearningRole = (userId, role) => data(http.patch(`/learning/admin/users/${userId}/role`, { role }))
export const fetchRoleChangeLogs = (params = {}) => data(http.get('/learning/admin/role-change-logs', { params }))
