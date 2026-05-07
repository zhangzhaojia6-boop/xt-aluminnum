import { api } from './index'

export async function fetchLiveAggregation(params = {}) {
  const { data } = await api.get('/aggregation/live', { params })
  return data
}

export async function fetchLiveActiveDate() {
  const { data } = await api.get('/aggregation/live/active-date')
  return data
}

export async function fetchLiveCellDetail(params = {}) {
  const { data } = await api.get('/aggregation/live/detail', { params })
  return data
}

export async function fetchPendingAssignmentEntries(params = {}) {
  const { data } = await api.get('/aggregation/live/pending-assignment', { params })
  return data
}
