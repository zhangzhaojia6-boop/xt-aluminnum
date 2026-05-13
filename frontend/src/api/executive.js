import { api } from './index'

export async function fetchExecutiveDashboard(date) {
  const params = date ? { date } : {}
  const { data } = await api.get('/executive/dashboard', { params })
  return data
}

export async function fetchMachineRanking(date) {
  const params = date ? { date } : {}
  const { data } = await api.get('/executive/machine-ranking', { params })
  return data
}

export async function fetchAluminumPriceTrend(days = 30) {
  const { data } = await api.get('/executive/aluminum-price-trend', { params: { days } })
  return data
}

export async function fetchProcessingFees(params = {}) {
  const { data } = await api.get('/executive/processing-fees', { params })
  return data
}

export async function createProcessingFee(payload) {
  const { data } = await api.post('/executive/processing-fees', payload)
  return data
}

export async function updateProcessingFee(ruleId, payload) {
  const { data } = await api.put(`/executive/processing-fees/${ruleId}`, payload)
  return data
}

export async function deleteProcessingFee(ruleId) {
  await api.delete(`/executive/processing-fees/${ruleId}`)
}

export async function recomputeExecutive(date) {
  const params = date ? { date } : {}
  const { data } = await api.post('/executive/recompute', null, { params })
  return data
}

export async function fetchAluminumPriceNow(date) {
  const params = date ? { date } : {}
  const { data } = await api.post('/executive/aluminum-price/fetch', null, { params })
  return data
}

export async function saveCostStrategySnapshot(tableModels, config = {}) {
  const { data } = await api.post('/executive/cost-strategy-snapshots', { tableModels }, config)
  return data
}
