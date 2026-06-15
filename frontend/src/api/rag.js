import { api } from './index.js'

export async function uploadRagDocument(file, metadata = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (metadata.source_name) formData.append('source_name', String(metadata.source_name).trim())
  if (metadata.version) formData.append('version', String(metadata.version).trim())
  if (metadata.workshop) formData.append('workshop', String(metadata.workshop).trim())
  if (metadata.owner) formData.append('owner', String(metadata.owner).trim())
  if (metadata.effective_date) formData.append('effective_date', String(metadata.effective_date).trim())
  if (metadata.permission_scope) formData.append('permission_scope', String(metadata.permission_scope).trim())
  const { data } = await api.post('/rag/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchRagDocuments() {
  const { data } = await api.get('/rag/documents')
  return data
}

export async function fetchRagDocument(documentId) {
  const { data } = await api.get(`/rag/documents/${documentId}`)
  return data
}

export async function deleteRagDocument(documentId) {
  const { data } = await api.delete(`/rag/documents/${documentId}`)
  return data
}

export async function queryRagKnowledge(payload) {
  const { data } = await api.post('/rag/query', payload)
  return data
}
