import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'

const runtimeApiBaseUrl = import.meta.env?.VITE_API_BASE_URL || '/api/v1'

export const apiBaseUrl = runtimeApiBaseUrl.replace(/\/$/, '')

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000
})

export function formatApiErrorMessage(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  if (detail) return detail
  if (error?.code === 'ECONNABORTED' || /timeout/i.test(String(error?.message || ''))) {
    return '请求超时，服务器响应太慢，请稍后重试'
  }
  if (error?.code === 'ERR_NETWORK' || /network error|failed to fetch/i.test(String(error?.message || ''))) {
    return '连接服务器失败，请检查网络、代理或稍后重试'
  }
  if (status >= 500) return '服务器暂时不可用，请稍后重试'
  return error?.message || '请求失败，请稍后重试'
}

export function setupApiInterceptors(router, pinia) {
  api.interceptors.request.use((config) => {
    const authStore = useAuthStore(pinia)
    if (authStore.token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  })

  api.interceptors.response.use(
    (response) => response,
    (error) => {
      const authStore = useAuthStore(pinia)
      const status = error?.response?.status
      const skipErrorToast = Boolean(error?.config?.skipErrorToast)
      const skipAuthLogout = Boolean(error?.config?.skipAuthLogout)
      const message = formatApiErrorMessage(error)

      if (status === 401 && !skipAuthLogout) {
        authStore.logout()
        if (router.currentRoute.value.name !== 'login') {
          router.push({ name: 'login' })
        }
      } else if (!skipErrorToast) {
        ElMessage.error(message)
      }
      return Promise.reject(error)
    }
  )
}
