import { api } from './index.js'

function mergeConfig(baseConfig = {}, overrideConfig = {}) {
  return {
    ...baseConfig,
    ...overrideConfig,
    headers: {
      ...(baseConfig.headers || {}),
      ...(overrideConfig.headers || {})
    }
  }
}

export async function fetchMobileBootstrap() {
  const { data } = await api.get('/mobile/bootstrap')
  return data
}

export async function fetchCurrentShift() {
  const { data } = await api.get('/mobile/current-shift')
  return data
}

export async function fetchWorkshopTemplate(templateKey) {
  const { data } = await api.get(`/templates/${templateKey}`)
  return data
}

export async function findWorkOrderByTrackingCard(trackingCardNo) {
  const response = await api.get(`/work-orders/${trackingCardNo}`, {
    validateStatus: (status) => status === 200 || status === 404
  })
  if (response.status === 404) return null
  return response.data
}

export async function createWorkOrder(payload, config = {}) {
  const { data } = await api.post('/work-orders/', payload, config)
  return data
}

export async function updateWorkOrder(workOrderId, payload, config = {}) {
  const { data } = await api.patch(`/work-orders/${workOrderId}`, payload, config)
  return data
}

export async function createWorkOrderEntry(workOrderId, payload, config = {}) {
  const { data } = await api.post(`/work-orders/${workOrderId}/entries`, payload, config)
  return data
}

export async function extractOcrFields({ workshopType, file }, config = {}) {
  const formData = new FormData()
  formData.append('workshop_type', workshopType)
  formData.append('file', file)
  const { data } = await api.post(
    '/ocr/extract',
    formData,
    mergeConfig(
      {
        headers: { 'Content-Type': 'multipart/form-data' }
      },
      config
    )
  )
  return data
}

export async function verifyOcrFields(payload, config = {}) {
  const { data } = await api.post('/ocr/verify', payload, config)
  return data
}

export async function updateWorkOrderEntry(entryId, payload, config = {}) {
  const { data } = await api.patch(`/work-orders/entries/${entryId}`, payload, config)
  return data
}

export async function submitWorkOrderEntry(entryId, payload = {}, config = {}) {
  const { data } = await api.post(`/work-orders/entries/${entryId}/submit`, payload, config)
  return data
}

export async function fetchMobileReport(businessDate, shiftId) {
  const { data } = await api.get(`/mobile/report/${businessDate}/${shiftId}`)
  return data
}

export async function saveMobileReport(payload) {
  const { data } = await api.post('/mobile/report/save', payload)
  return data
}

export async function submitMobileReport(payload) {
  const { data } = await api.post('/mobile/report/submit', payload)
  return data
}

export async function uploadMobileReportPhoto({ businessDate, shiftId, file }) {
  const formData = new FormData()
  formData.append('business_date', businessDate)
  formData.append('shift_id', String(shiftId))
  formData.append('file', file)
  const { data } = await api.post('/mobile/report/upload-photo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchMobileHistory(params = {}) {
  const { data } = await api.get('/mobile/report/history', { params })
  return data
}

export async function fetchMobileReminders(params = {}) {
  const { data } = await api.get('/mobile/reminders', { params })
  return data
}

export async function runMobileReminders(params = {}) {
  const { data } = await api.post('/mobile/reminders/run', null, { params })
  return data
}

export async function ackMobileReminder(reminderId, note = '') {
  const { data } = await api.post(`/mobile/reminders/${reminderId}/ack`, { note })
  return data
}

export async function closeMobileReminder(reminderId, note = '') {
  const { data } = await api.post(`/mobile/reminders/${reminderId}/close`, { note })
  return data
}
