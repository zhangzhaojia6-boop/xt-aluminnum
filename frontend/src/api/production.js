import { api } from './index'

export async function importProductionFile(file, templateCode = null, duplicateStrategy = 'reject') {
  const formData = new FormData()
  formData.append('file', file)
  if (templateCode) {
    formData.append('template_code', templateCode)
  }
  formData.append('duplicate_strategy', duplicateStrategy)
  const { data } = await api.post('/production/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchShiftProductionData(params = {}) {
  const { data } = await api.get('/production/shift-data', { params })
  return data
}

export async function fetchShiftProductionDetail(id) {
  const { data } = await api.get(`/production/shift-data/${id}`)
  return data
}

export async function fetchProductionExceptions(params = {}) {
  const { data } = await api.get('/production/exceptions', { params })
  return data
}

export async function reviewShiftData(id, reason = null) {
  const { data } = await api.post(`/production/shift-data/${id}/review`, { reason })
  return data
}

export async function confirmShiftData(id, reason = null) {
  const { data } = await api.post(`/production/shift-data/${id}/confirm`, { reason })
  return data
}

export async function rejectShiftData(id, reason) {
  const { data } = await api.post(`/production/shift-data/${id}/reject`, { reason })
  return data
}

export async function voidShiftData(id, reason) {
  const { data } = await api.post(`/production/shift-data/${id}/void`, { reason })
  return data
}
