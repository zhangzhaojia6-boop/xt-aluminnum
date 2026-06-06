import { api } from './index.js'

export async function fetchEnergySummary(params = {}) {
  const { data } = await api.get('/energy/summary', {
    params,
    skipAuthLogout: true,
    skipErrorToast: true,
  })
  return data
}
