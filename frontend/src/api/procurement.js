import { api } from './index.js'

const BASE = '/procurement'

export function formatMoney(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'
}

export const fetchProcurementMeta = () => api.get(`${BASE}/meta`, { skipErrorToast: true }).then((res) => res.data)
export const fetchProcurementRequests = (scope = 'todo') => api.get(`${BASE}/requests`, { params: { scope } }).then((res) => res.data)
export const fetchProcurementRequest = (id) => api.get(`${BASE}/requests/${id}`).then((res) => res.data)
export const createProcurementRequest = (body) => api.post(`${BASE}/requests`, body).then((res) => res.data)
export const actOnProcurementRequest = (id, body) => api.post(`${BASE}/requests/${id}/actions`, body).then((res) => res.data)
export const fetchProcurementBoard = () => api.get(`${BASE}/board`).then((res) => res.data)
export const fetchProcurementLedger = (params) => api.get(`${BASE}/ledger`, { params, skipErrorToast: true }).then((res) => res.data)
export const voidProcurementRequest = (id, reason) => api.post(`${BASE}/requests/${id}/void`, { reason }).then((res) => res.data)
export const fetchProcurementSuppliers = () => api.get(`${BASE}/suppliers`, { skipErrorToast: true }).then((res) => res.data)
export const saveProcurementSupplier = (id, body) => (id
  ? api.put(`${BASE}/suppliers/${id}`, body)
  : api.post(`${BASE}/suppliers`, body)).then((res) => res.data)

export async function downloadProcurementLedger(params) {
  const res = await api.get(`${BASE}/ledger.csv`, { params, responseType: 'blob', skipErrorToast: true })
  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `采购台账-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export const fetchProcurementAssignments = () => api.get(`${BASE}/assignments`).then((res) => res.data)
export const saveProcurementAssignment = (body) => api.post(`${BASE}/assignments`, body).then((res) => res.data)

export function uploadProcurementDocument(id, docType, file) {
  const form = new FormData()
  form.append('doc_type', docType)
  form.append('file', file)
  return api.post(`${BASE}/requests/${id}/documents`, form).then((res) => res.data)
}

export async function openProcurementDocument(documentId) {
  const res = await api.get(`${BASE}/documents/${documentId}/file`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
