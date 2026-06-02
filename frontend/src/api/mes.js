import { api } from './index.js'

export async function importMesExport(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/mes/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchMesSyncStatus() {
  const { data } = await api.get('/mes/sync-status')
  return data
}

export async function fetchMesSyncRuns(params = {}) {
  const { data } = await api.get('/mes/sync-runs', { params })
  return data
}

export async function fetchMesExtendedSummary(params = {}) {
  const { data } = await api.get('/mes/extended/summary', { params })
  return data
}

export async function fetchMesWorkshopProcessRecords(params = {}) {
  const { data } = await api.get('/mes/extended/workshop-process-records', { params })
  return data
}

export async function fetchMesMaterialRecords(params = {}) {
  const { data } = await api.get('/mes/extended/material-records', { params })
  return data
}

export async function fetchMesWipTotalSnapshots(params = {}) {
  const { data } = await api.get('/mes/extended/wip-total-snapshots', { params })
  return data
}
