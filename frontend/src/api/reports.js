import { api } from './index.js'

function unwrapItems(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.items)) return payload.items
  return []
}

export async function fetchReports(params = {}) {
  const { data } = await api.get('/reports', { params })
  return unwrapItems(data)
}

export async function previewTemplateDailyReport(targetDate) {
  const { data } = await api.post('/reports/template-daily/preview', { target_date: targetDate })
  return data
}
