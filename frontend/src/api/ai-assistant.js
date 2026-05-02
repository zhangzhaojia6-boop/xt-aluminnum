import { api } from './index'

export async function fetchAssistantConversations() {
  const { data } = await api.get('/ai/assistant/conversations')
  return data
}

export async function createAssistantConversation(payload = {}) {
  const { data } = await api.post('/ai/assistant/conversations', payload)
  return data
}

export async function fetchAssistantMessages(conversationId) {
  const { data } = await api.get(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}/messages`)
  return data
}

export async function sendAssistantMessage(conversationId, payload = {}) {
  const { data } = await api.post(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}/messages`, payload)
  return data
}

export async function askAssistant(payload = {}) {
  const { data } = await api.post('/ai/assistant/ask', payload)
  return data
}

export async function fetchBriefings() {
  const { data } = await api.get('/ai/briefings')
  return data
}

export async function markBriefingRead(id) {
  const { data } = await api.post(`/ai/briefings/${encodeURIComponent(id)}/read`)
  return data
}

export async function followUpBriefing(id) {
  const { data } = await api.post(`/ai/briefings/${encodeURIComponent(id)}/follow-up`)
  return data
}

export async function generateBriefingNow(payload = {}) {
  const { data } = await api.post('/ai/briefings/generate-now', payload)
  return data
}

export async function fetchWatchlist() {
  const { data } = await api.get('/ai/watchlist')
  return data
}

export async function createWatchlistItem(payload = {}) {
  const { data } = await api.post('/ai/watchlist', payload)
  return data
}

export async function updateWatchlistItem(id, payload = {}) {
  const { data } = await api.patch(`/ai/watchlist/${encodeURIComponent(id)}`, payload)
  return data
}

export async function deleteWatchlistItem(id) {
  const { data } = await api.delete(`/ai/watchlist/${encodeURIComponent(id)}`)
  return data
}
