import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'

const runtimeApiBaseUrl = import.meta.env?.VITE_API_BASE_URL || '/api/v1'

export const apiBaseUrl = runtimeApiBaseUrl.replace(/\/$/, '')

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000
})

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
      const detail = error?.response?.data?.detail
      const skipErrorToast = Boolean(error?.config?.skipErrorToast)
      const message = Array.isArray(detail)
        ? detail.map((item) => item?.msg || item).join('; ')
        : detail || error?.message || '请求失败，请检查网络'

      if (status === 401) {
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
