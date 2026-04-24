import { api } from './index.js'

export async function loginApi({ username, password }) {
  const { data } = await api.post('/auth/login', { username, password })
  return data
}

export async function dingtalkLoginApi({ code }) {
  const { data } = await api.post('/dingtalk/login', { code })
  return {
    ...data,
    access_token: data.access_token || data.token || '',
    token_type: data.token_type || 'bearer'
  }
}

export async function qrLoginApi({ qr_code }) {
  const { data } = await api.post('/auth/qr-login', { qr_code })
  return data
}

export async function meApi(config = {}) {
  const { data } = await api.get('/auth/me', config)
  return data
}
