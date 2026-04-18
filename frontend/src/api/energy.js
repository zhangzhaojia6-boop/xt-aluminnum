import { api } from './index'

export async function importEnergyFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/energy/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchEnergySummary(params = {}) {
  const { data } = await api.get('/energy/summary', { params })
  return data
}
