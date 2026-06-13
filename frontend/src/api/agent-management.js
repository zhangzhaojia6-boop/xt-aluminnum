import { api } from './index.js'

export async function fetchAgentManagementOverview(params = {}) {
  const { data } = await api.get('/agent-management/overview', { params })
  return data
}

export async function fetchAgentKnowledgeEntries() {
  const { data } = await api.get('/agent-management/knowledge')
  return data
}

export async function askAgentKnowledge(question) {
  const { data } = await api.post('/agent-management/knowledge/answer', { question })
  return data
}
