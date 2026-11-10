import { api } from './index.js'

export async function fetchAnomalyNote(businessDate) {
  const { data } = await api.get(`/daily-anomaly-notes/${businessDate}`, {
    skipAuthLogout: true,
    skipErrorToast: true,
  })
  return data
}

export async function saveAnomalyNote(businessDate, content) {
  const { data } = await api.put(`/daily-anomaly-notes/${businessDate}`, { content }, {
    skipAuthLogout: true,
    skipErrorToast: true,
  })
  return data
}
