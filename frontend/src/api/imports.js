import { api } from './index.js'

export async function fetchImportHistory() {
  const { data } = await api.get('/imports/history')
  return data
}

export async function fetchDailyProductionMappingPreview(batchId) {
  const params = batchId ? { batch_id: batchId } : undefined
  const { data } = await api.get('/imports/daily-production/mapping-preview', { params })
  return data
}

export const listImportBatches = fetchImportHistory
