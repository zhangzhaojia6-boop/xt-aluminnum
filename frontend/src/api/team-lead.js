import { api } from './index.js'

export async function fetchTeamLeadOverview(params = {}) {
  const { data } = await api.get('/team-lead/overview', { params })
  return data
}
