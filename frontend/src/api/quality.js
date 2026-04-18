import { api } from './index'

export async function runQualityChecks(payload) {
  const { data } = await api.post('/quality/run-checks', payload)
  return data
}

export async function fetchQualityIssues(params = {}) {
  const { data } = await api.get('/quality/issues', { params })
  return data
}

export async function resolveQualityIssue(id, note = null) {
  const { data } = await api.post(`/quality/issues/${id}/resolve`, { note })
  return data
}

export async function ignoreQualityIssue(id, note = null) {
  const { data } = await api.post(`/quality/issues/${id}/ignore`, { note })
  return data
}
