import { api } from './index.js'

function unwrapItems(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.items)) return payload.items
  return []
}

export async function runQualityChecks(payload) {
  const { data } = await api.post('/quality/run-checks', payload)
  return data
}

export async function fetchQualityIssues(params = {}) {
  const { data } = await api.get('/quality/issues', { params })
  return unwrapItems(data)
}

export async function resolveQualityIssue(id, note) {
  const { data } = await api.post(`/quality/issues/${id}/resolve`, { note })
  return data
}

export async function ignoreQualityIssue(id, note) {
  const { data } = await api.post(`/quality/issues/${id}/ignore`, { note })
  return data
}
