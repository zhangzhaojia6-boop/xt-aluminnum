import { api } from './index'

export async function generateReport(payload) {
  const { data } = await api.post('/reports/generate', payload)
  return data
}

export async function fetchReports(params = {}) {
  const { data } = await api.get('/reports', { params })
  return data
}

export async function fetchReportDetail(id) {
  const { data } = await api.get(`/reports/${id}`)
  return data
}

export async function reviewReport(id, note = null) {
  const { data } = await api.post(`/reports/${id}/review`, { note })
  return data
}

export async function publishReport(id, note = null) {
  const { data } = await api.post(`/reports/${id}/publish`, { note })
  return data
}

export async function runDailyPipeline(payload) {
  const { data } = await api.post('/reports/run-daily-pipeline', payload)
  return data
}

export async function finalizeReport(id, note = null, force = false) {
  const { data } = await api.post(`/reports/${id}/finalize`, { note, force })
  return data
}

export async function exportReport(id, format = 'json') {
  const { data, headers } = await api.get(`/reports/${id}/export`, {
    params: { format },
    responseType: 'blob'
  })
  return { data, headers }
}
