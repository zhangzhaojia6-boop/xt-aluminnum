import { api } from './index.js'

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

export async function fetchLiveFillDetails(params = {}) {
  const { data } = await api.get('/aggregation/live/fill-details', { params })
  return data
}

export async function fetchPendingAssignmentEntries(params = {}) {
  const { data } = await api.get('/aggregation/live/pending-assignment', { params })
  return data
}

export async function resolveMissingOutputWeight(entryId, payload = {}) {
  const { data } = await api.patch(`/aggregation/live/missing-output/${entryId}`, payload, { skipErrorToast: true })
  return data
}
