import { api } from './index.js'

function unwrapPage(payload) {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length,
      skip: 0,
      limit: payload.length
    }
  }
  return {
    items: Array.isArray(payload?.items) ? payload.items : [],
    total: Number(payload?.total || 0),
    skip: Number(payload?.skip || 0),
    limit: Number(payload?.limit || 0)
  }
}

export async function fetchUsersPage(params = {}) {
  return unwrapPage((await api.get('/users/', { params })).data)
}

export async function createUser(payload) {
  return (await api.post('/users/', payload)).data
}

export async function updateUser(id, payload) {
  return (await api.put(`/users/${id}`, payload)).data
}

export async function deleteUser(id) {
  return (await api.delete(`/users/${id}`)).data
}

export async function resetUserPassword(id, payload) {
  return (await api.post(`/users/${id}/reset-password`, payload)).data
}
