import { api } from './index.js'

export async function fetchEnergyLatestDataDate() {
  const { data } = await api.get('/energy/latest-data-date', {
    skipAuthLogout: true,
    skipErrorToast: true,
  })
  return data?.business_date || ''
}

export async function fetchEnergySummary(params = {}) {
  const { data } = await api.get('/energy/summary', {
    params,
    skipAuthLogout: true,
    skipErrorToast: true,
  })
  return data
}
