import { api } from './index.js'

const BASE = '/procurement'

export const fetchProcurementMeta = () => api.get(`${BASE}/meta`, { skipErrorToast: true }).then((res) => res.data)
export const fetchProcurementRequests = (scope = 'todo') => api.get(`${BASE}/requests`, { params: { scope } }).then((res) => res.data)
export const fetchProcurementRequest = (id) => api.get(`${BASE}/requests/${id}`).then((res) => res.data)
export const createProcurementRequest = (body) => api.post(`${BASE}/requests`, body).then((res) => res.data)
export const actOnProcurementRequest = (id, body) => api.post(`${BASE}/requests/${id}/actions`, body).then((res) => res.data)
export const fetchProcurementBoard = () => api.get(`${BASE}/board`).then((res) => res.data)

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
