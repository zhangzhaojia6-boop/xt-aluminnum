import { api } from './index'

export async function uploadImportFile(formData) {
  const { data } = await api.post('/imports/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function fetchImportHistory() {
  const { data } = await api.get('/imports/history')
  return data
}

export const uploadImport = async (file, importType = 'generic') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('import_type', importType)
  return uploadImportFile(formData)
}

export const listImportBatches = fetchImportHistory
