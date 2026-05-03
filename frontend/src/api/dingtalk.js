import { api } from './index.js'

export async function dingtalkH5LoginApi({ code }) {
  const { data } = await api.post('/dingtalk/h5-login', { code })
  return {
    ...data,
    access_token: data.access_token || data.token || '',
    token_type: data.token_type || 'bearer'
  }
}
