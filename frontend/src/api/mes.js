import { api } from './index'

export async function importMesExport(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/mes/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}
