import { api } from './index'

export async function generateReconciliation(payload) {
  const { data } = await api.post('/reconciliation/generate', payload)
  return data
}

export async function fetchReconciliationItems(params = {}) {
  const { data } = await api.get('/reconciliation/items', { params })
  return data
}

export async function confirmReconciliationItem(id, note = null) {
  const { data } = await api.post(`/reconciliation/items/${id}/confirm`, { note })
  return data
}

export async function ignoreReconciliationItem(id, note = null) {
  const { data } = await api.post(`/reconciliation/items/${id}/ignore`, { note })
  return data
}

export async function correctReconciliationItem(id, note) {
  const { data } = await api.post(`/reconciliation/items/${id}/correct`, { note })
  return data
}
