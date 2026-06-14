import { api } from './index.js'

export async function uploadRagDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
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
