import { api } from './index.js'

export async function fetchMappingReconciliationSources() {
  const { data } = await api.get('/mapping-reconciliation/sources')
  return data
}

export async function runMappingReconciliation(payload) {
  const { data } = await api.post('/mapping-reconciliation/run', payload)
  return data
}
