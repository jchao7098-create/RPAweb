import axios from 'axios'
import { clearLearningSession, getLearningToken } from '@/utils/learningSession'

// 统一的后端地址：优先读环境变量（在 frontend/.env.development 中配置
// VITE_API_BASE_URL=http://xxx:5000 即可覆盖），未配置时退回当前内网地址。
// 新代码一律从这里拿实例，不要再在组件里硬编码 IP。
const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const http = axios.create({
  baseURL,
  timeout: 30000,
})

const isLearningRequest = (config) => typeof config?.url === 'string' && config.url.startsWith('/learning')
const isUserManagementRequest = (config) =>
  typeof config?.url === 'string'
  && (
    config.url.startsWith('/user/manage')
    || config.url.startsWith('/user/requirements/')
    || config.url.startsWith('/user/assets')
    || config.url === '/user/submit_requirement'
    || config.url === '/user/get_my_requirements'
  )
const isAdminExportRequest = (config) =>
  typeof config?.url === 'string' && config.url.startsWith('/admin/export/')
const isAdminProgressUpdate = (config) =>
  typeof config?.url === 'string'
  && (
    config.url === '/admin/update_progress'
    || config.url === '/admin/assets/progress'
  )

http.interceptors.request.use((config) => {
  if (
    isLearningRequest(config)
    || isUserManagementRequest(config)
    || isAdminExportRequest(config)
    || isAdminProgressUpdate(config)
  ) {
    const token = getLearningToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401
      && (
        isLearningRequest(error.config)
        || isUserManagementRequest(error.config)
        || isAdminExportRequest(error.config)
        || isAdminProgressUpdate(error.config)
      )
    ) {
      clearLearningSession()
    }
    return Promise.reject(error)
  },
)

export default http
