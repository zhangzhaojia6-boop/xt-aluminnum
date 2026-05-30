import { api } from './index.js'

export async function fetchUserPreferences(config = {}) {
  const { data } = await api.get('/user/preferences', { skipErrorToast: true, skipAuthLogout: true, ...config })
  return data
}

export async function updateUserPreferences(payload, config = {}) {
  const { data } = await api.put('/user/preferences', payload, { skipErrorToast: true, ...config })
  return data
}
