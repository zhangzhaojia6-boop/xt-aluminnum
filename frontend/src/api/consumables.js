import { api } from './index.js'

export async function fetchConsumableWorkshops() {
  const { data } = await api.get('/consumables/workshops')
  return data
}

export async function fetchDailyConsumableLog(params) {
  const { data } = await api.get('/consumables/daily', { params })
  return data
}

export async function upsertDailyConsumableLog(payload) {
  const { data } = await api.post('/consumables/daily', payload)
  return data
}
