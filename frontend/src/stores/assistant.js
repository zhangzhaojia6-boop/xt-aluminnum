import { defineStore } from 'pinia'

import {
  buildAssistantFallback,
  fetchAssistantCapabilities,
  fetchAssistantLiveProbe,
  queryAssistant
} from '../api/assistant'

export const useAssistantStore = defineStore('assistant', {
  state: () => ({
    capabilities: buildAssistantFallback(),
    liveProbe: null,
    loadingCapabilities: false,
    loadingProbe: false,
    querying: false,
    history: [],
    lastError: ''
  }),
  actions: {
    async loadCapabilities(force = false) {
      if (this.loadingCapabilities) return this.capabilities
      if (!force && this.capabilities?.capabilities?.length) return this.capabilities
      this.loadingCapabilities = true
      this.lastError = ''
      try {
        this.capabilities = await fetchAssistantCapabilities()
        return this.capabilities
      } catch (error) {
        this.lastError = error?.message || '加载 AI 能力失败'
        return this.capabilities
      } finally {
        this.loadingCapabilities = false
      }
    },
    async loadLiveProbe() {
      if (this.loadingProbe) return this.liveProbe
      this.loadingProbe = true
      this.lastError = ''
      try {
        this.liveProbe = await fetchAssistantLiveProbe()
        return this.liveProbe
      } catch (error) {
        this.lastError = error?.message || '加载 AI 探针失败'
        return null
      } finally {
        this.loadingProbe = false
      }
    },
    async ask(query, mode = 'answer') {
      const prompt = String(query || '').trim()
      if (!prompt) return null
      this.querying = true
      this.lastError = ''
      try {
        const response = await queryAssistant({ query: prompt, mode })
        this.history.unshift({
          at: new Date().toISOString(),
          query: prompt,
          mode,
          response
        })
        this.history = this.history.slice(0, 20)
        return response
      } catch (error) {
        this.lastError = error?.message || 'AI 查询失败'
        throw error
      } finally {
        this.querying = false
      }
    }
  }
})

