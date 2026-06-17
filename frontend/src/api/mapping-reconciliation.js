import { api } from './index.js'

export async function fetchMappingReconciliationSources(params = {}) {
  const { data } = await api.get('/mapping-reconciliation/sources', { params })
  return data
}

export async function runMappingReconciliation(payload) {
  const { data } = await api.post('/mapping-reconciliation/run', payload)
  return data
}

export async function proposeMappingReconciliationRules(payload) {
  const { data } = await api.post('/mapping-reconciliation/rules/propose', payload)
  return data
}

export async function applyMappingReconciliationRulesDryRun(payload) {
  const { data } = await api.post('/mapping-reconciliation/rules/apply-dry-run', payload)
  return data
}
