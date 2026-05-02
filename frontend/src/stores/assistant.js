import { defineStore } from 'pinia'

import {
  buildAssistantFallback,
  fetchAssistantCapabilities,
  fetchAssistantLiveProbe,
  queryAssistant
} from '../api/assistant'
import {
  createWatchlistItem,
  fetchBriefings,
  fetchWatchlist,
  followUpBriefing,
  generateBriefingNow,
  markBriefingRead,
  updateWatchlistItem
} from '../api/ai-assistant'
import { normalizeBriefing, normalizeWatchlistItem } from '../utils/aiAssistantContracts'

export const useAssistantStore = defineStore('assistant', {
  state: () => ({
    capabilities: buildAssistantFallback(),
    liveProbe: null,
    loadingCapabilities: false,
    loadingProbe: false,
    querying: false,
    history: [],
    briefings: [],
    watchlist: [],
    loadingBriefings: false,
    loadingWatchlist: false,
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
    },
    async loadBriefings() {
      if (this.loadingBriefings) return this.briefings
      this.loadingBriefings = true
      this.lastError = ''
      try {
        const rows = await fetchBriefings()
        this.briefings = rows.map(normalizeBriefing)
        return this.briefings
      } catch (error) {
        this.lastError = error?.message || '加载主动汇报失败'
        throw error
      } finally {
        this.loadingBriefings = false
      }
    },
    async generateBriefing(briefingType = 'opening_shift') {
      const briefing = normalizeBriefing(await generateBriefingNow({ briefing_type: briefingType }))
      this.briefings = [briefing, ...this.briefings.filter((item) => item.id !== briefing.id)]
      return briefing
    },
    async markBriefingRead(id) {
      const briefing = normalizeBriefing(await markBriefingRead(id))
      this.briefings = this.briefings.map((item) => (item.id === briefing.id ? briefing : item))
      return briefing
    },
    async followUpBriefing(id) {
      const briefing = normalizeBriefing(await followUpBriefing(id))
      this.briefings = this.briefings.map((item) => (item.id === briefing.id ? briefing : item))
      return briefing
    },
    async loadWatchlist() {
      if (this.loadingWatchlist) return this.watchlist
      this.loadingWatchlist = true
      this.lastError = ''
      try {
        const rows = await fetchWatchlist()
        this.watchlist = rows.map(normalizeWatchlistItem)
        return this.watchlist
      } catch (error) {
        this.lastError = error?.message || '加载关注列表失败'
        throw error
      } finally {
        this.loadingWatchlist = false
      }
    },
    async createWatch(payload) {
      const watch = normalizeWatchlistItem(await createWatchlistItem(payload))
      this.watchlist = [watch, ...this.watchlist.filter((item) => item.id !== watch.id)]
      return watch
    },
    async updateWatch(id, payload) {
      const watch = normalizeWatchlistItem(await updateWatchlistItem(id, payload))
      this.watchlist = this.watchlist.map((item) => (item.id === watch.id ? watch : item))
      return watch
    }
  }
})

