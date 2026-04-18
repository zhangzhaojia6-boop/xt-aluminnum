import { api } from './index'

export async function importSchedules(file, templateCode = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (templateCode) {
    formData.append('template_code', templateCode)
  }
  const { data } = await api.post('/attendance/schedules/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function importClocks(file, templateCode = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (templateCode) {
    formData.append('template_code', templateCode)
  }
  const { data } = await api.post('/attendance/clocks/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchSchedules(params = {}) {
  const { data } = await api.get('/attendance/schedules', { params })
  return data
}

export async function fetchClocks(params = {}) {
  const { data } = await api.get('/attendance/clocks', { params })
  return data
}

export async function processAttendance(payload) {
  const { data } = await api.post('/attendance/process', payload)
  return data
}

export async function fetchAttendanceResults(params) {
  const { data } = await api.get('/attendance/results', { params })
  return data
}

export async function fetchAttendanceDetail(employeeId, businessDate) {
  const { data } = await api.get(`/attendance/results/${employeeId}/${businessDate}`)
  return data
}

export async function fetchAttendanceExceptions(params) {
  const { data } = await api.get('/attendance/exceptions', { params })
  return data
}

export async function resolveAttendanceException(id, payload) {
  const { data } = await api.post(`/attendance/exceptions/${id}/resolve`, payload)
  return data
}

export async function overrideAttendanceResult(id, payload) {
  const { data } = await api.post(`/attendance/results/${id}/override`, payload)
  return data
}

export async function fetchAttendanceDraft(params) {
  const { data } = await api.get('/attendance/draft', { params })
  return data
}

export async function submitAttendanceConfirmation(payload, config = {}) {
  const { data } = await api.post('/attendance/confirm', payload, config)
  return data
}

export async function fetchAttendanceAnomalies(params) {
  const { data } = await api.get('/attendance/anomalies', { params })
  return data
}

export async function reviewAttendanceAnomaly(detailId, payload) {
  const { data } = await api.patch(`/attendance/anomalies/${detailId}/review`, payload)
  return data
}

export async function fetchAttendanceSummary(params) {
  const { data } = await api.get('/attendance/summary', { params })
  return data
}
