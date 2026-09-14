import { defineStore } from 'pinia'
import axios from 'axios'

import { apiBaseUrl, formatApiErrorMessage } from '../api'
import {
  createAssistantConversation,
  fetchAiRuntime,
  fetchAssistantConversations,
  fetchAssistantMessages,
  sendAssistantMessage
} from '../api/ai-assistant'
import { useAuthStore } from './auth'

const aiBaseUrl = `${apiBaseUrl}/ai`

const aiApi = axios.create({
  baseURL: aiBaseUrl,
  timeout: 30000
})

function authHeaders() {
  const authStore = useAuthStore()
  return authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
}

aiApi.interceptors.request.use((config) => {
  config.headers = {
    ...config.headers,
    ...authHeaders()
  }
  return config
})

function normalizeConversation(conversation) {
  return {
    id: conversation?.id ?? conversation?.conversation_id ?? '',
    title: conversation?.title || '新对话',
    created_at: conversation?.created_at || conversation?.createdAt || '',
    updated_at: conversation?.updated_at || conversation?.updatedAt || ''
  }
}

function normalizeMessage(message) {
  const answer = message?.payload?.answer || {}
  return {
    role: message?.role || 'assistant',
    content: message?.content || '',
    timestamp: message?.timestamp || message?.created_at || Date.now(),
    toolCalls: message?.toolCalls || message?.tool_calls || answer.evidence_refs || answer.evidenceRefs || [],
    missingData: message?.missingData || answer.missing_data || answer.missingData || [],
    payload: message?.payload || null
  }
}

function resolveConversationList(data) {
  const items = Array.isArray(data) ? data : data?.items || data?.conversations || []
  return items.map(normalizeConversation).filter((conversation) => conversation.id)
}

function resolveMessageList(data) {
  const items = Array.isArray(data) ? data : data?.messages || []
  return items.map(normalizeMessage)
}

export const useAiChatStore = defineStore('ai-chat', {
  state: () => ({
    conversations: [],
    currentId: null,
    messages: [],
    loadingConversations: false,
    loadingMessages: false,
    loadingRuntime: false,
    streaming: false,
    runtime: null,
    lastError: '',
    abortController: null
  }),
  getters: {
    currentConversation: (state) => state.conversations.find((conversation) => conversation.id === state.currentId) || null
  },
  actions: {
    async loadConversations() {
      this.loadingConversations = true
      this.lastError = ''
      try {
        let data
        try {
          data = await fetchAssistantConversations()
        } catch {
          const response = await aiApi.get('/conversations')
          data = response.data
        }
        this.conversations = resolveConversationList(data)
        return this.conversations
      } catch (error) {
        this.lastError = error?.response?.data?.detail || error?.message || '加载对话失败'
        throw error
      } finally {
        this.loadingConversations = false
      }
    },
    async loadRuntime() {
      if (this.loadingRuntime) return this.runtime
      this.loadingRuntime = true
      try {
        this.runtime = await fetchAiRuntime()
        return this.runtime
      } catch {
        this.runtime = {
          engine: 'unknown',
          llm_configured: false,
          model_ref_set: false,
          canonical_entry: '/manage/ai-assistant',
          legacy_llm_entry: '/api/v1/assistant'
        }
        return this.runtime
      } finally {
        this.loadingRuntime = false
      }
    },
    async loadMessages(conversationId) {
      if (!conversationId || this.loadingMessages || this.streaming) return
      this.loadingMessages = true
      this.lastError = ''
      this.currentId = conversationId
      try {
        let data
        try {
          data = await fetchAssistantMessages(conversationId)
        } catch {
          const response = await aiApi.get(`/conversations/${conversationId}`)
          data = response.data
        }
        this.messages = resolveMessageList(data)
      } catch (error) {
        this.lastError = error?.response?.data?.detail || error?.message || '加载消息失败'
        throw error
      } finally {
        this.loadingMessages = false
      }
    },
    async createConversation(payload = {}) {
      this.lastError = ''
      try {
        const data = await createAssistantConversation(payload)
        const conversation = normalizeConversation(data)
        if (conversation.id) {
          this.conversations = [conversation, ...this.conversations.filter((item) => item.id !== conversation.id)]
          this.currentId = conversation.id
          this.messages = []
        }
        return conversation
      } catch (error) {
        try {
          const { data } = await aiApi.post('/conversations')
          const conversation = normalizeConversation(data)
          if (conversation.id) {
            this.conversations = [conversation, ...this.conversations.filter((item) => item.id !== conversation.id)]
            this.currentId = conversation.id
            this.messages = []
          }
          return conversation
        } catch (fallbackError) {
          this.lastError = fallbackError?.response?.data?.detail || fallbackError?.message || error?.message || '创建对话失败'
          throw fallbackError
        }
      }
    },
    async deleteConversation(id) {
      if (!id || this.streaming) return
      this.lastError = ''
      try {
        await aiApi.delete(`/conversations/${id}`)
        this.conversations = this.conversations.filter((conversation) => conversation.id !== id)
        if (this.currentId === id) {
          this.currentId = null
          this.messages = []
        }
      } catch (error) {
        this.lastError = error?.response?.data?.detail || error?.message || '删除对话失败'
        throw error
      }
    },
    async renameConversation(id, title) {
      const nextTitle = String(title || '').trim()
      if (!id || !nextTitle) return
      this.lastError = ''
      try {
        const { data } = await aiApi.patch(`/conversations/${id}`, { title: nextTitle })
        const conversation = this.conversations.find((item) => item.id === id)
        if (conversation) {
          conversation.title = data?.title || nextTitle
          conversation.updated_at = data?.updated_at || conversation.updated_at
        }
      } catch (error) {
        this.lastError = error?.response?.data?.detail || error?.message || '重命名失败'
        throw error
      }
    },
    async sendMessage(content, options = {}) {
      const text = String(content || '').trim()
      if (!text || this.streaming) return
      const messageScope = options.scope || options.context?.scope || null
      const messageIntent = options.intent || 'factory_status'
      if (!this.currentId) await this.createConversation(messageScope ? { scope: messageScope } : {})

      const userMessage = normalizeMessage({ role: 'user', content: text })
      this.messages.push(userMessage, normalizeMessage({ role: 'assistant', content: '', toolCalls: [] }))
      const assistantMessage = this.messages[this.messages.length - 1]
      this.streaming = true
      this.lastError = ''
      const controller = new AbortController()
      this.abortController = controller
      const conversationId = this.currentId

      try {
        const data = await sendAssistantMessage(conversationId, {
          content: text,
          intent: messageIntent,
          scope: messageScope || undefined
        }, { signal: controller.signal, skipErrorToast: true })
        if (controller.signal.aborted) return
        const answer = data?.answer || data?.assistant_message?.payload?.answer || {}
        assistantMessage.content = answer.answer || data?.assistant_message?.content || ''
        assistantMessage.toolCalls = answer.evidence_refs || []
        assistantMessage.missingData = answer.missing_data || []
        assistantMessage.payload = { answer }
        const conversation = this.conversations.find((item) => item.id === conversationId)
        if (conversation) conversation.updated_at = new Date().toISOString()
        return data
      } catch (error) {
        if (controller.signal.aborted) {
          assistantMessage.content = '已停止'
        } else {
          assistantMessage.content = assistantMessage.content || '生成失败，请稍后重试'
          this.lastError = formatApiErrorMessage(error)
          throw error
        }
      } finally {
        if (this.abortController === controller) {
          this.streaming = false
          this.abortController = null
        }
      }
    },
    async stopGeneration() {
      if (!this.streaming) return
      this.abortController?.abort()
    }
  }
})
