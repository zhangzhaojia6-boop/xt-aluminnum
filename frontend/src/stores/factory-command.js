import { defineStore } from 'pinia'

import {
  fetchFactoryCommandCoilFlow,
  fetchFactoryCommandCoils,
  fetchFactoryCommandCostBenefit,
  fetchFactoryCommandDestinations,
  fetchFactoryCommandMachineLines,
  fetchFactoryCommandOverview,
  fetchFactoryCommandWorkshops
} from '../api/factory-command'

export const useFactoryCommandStore = defineStore('factory-command', {
  state: () => ({
    overview: null,
    workshops: [],
    machineLines: [],
    coils: [],
    coilFlows: {},
    costBenefit: null,
    destinations: [],
    loading: false,
    lastError: ''
  }),
  actions: {
    async loadOverview() {
      this.overview = await fetchFactoryCommandOverview()
      return this.overview
    },
    async loadWorkshops() {
      this.workshops = await fetchFactoryCommandWorkshops()
      return this.workshops
    },
    async loadMachineLines() {
      this.machineLines = await fetchFactoryCommandMachineLines()
      return this.machineLines
    },
    async loadCoils(params = {}) {
      this.coils = await fetchFactoryCommandCoils(params)
      return this.coils
    },
    async loadCoilFlow(coilKey) {
      const flow = await fetchFactoryCommandCoilFlow(coilKey)
      this.coilFlows = { ...this.coilFlows, [coilKey]: flow }
      return flow
    },
    async loadCostBenefit() {
      this.costBenefit = await fetchFactoryCommandCostBenefit()
      return this.costBenefit
    },
    async loadDestinations() {
      this.destinations = await fetchFactoryCommandDestinations()
      return this.destinations
    },
    async loadAll() {
      this.loading = true
      this.lastError = ''
      try {
        const [overview, workshops, machineLines, coils, costBenefit, destinations] = await Promise.all([
          fetchFactoryCommandOverview(),
          fetchFactoryCommandWorkshops(),
          fetchFactoryCommandMachineLines(),
          fetchFactoryCommandCoils(),
          fetchFactoryCommandCostBenefit(),
          fetchFactoryCommandDestinations()
        ])
        this.overview = overview
        this.workshops = workshops
        this.machineLines = machineLines
        this.coils = coils
        this.costBenefit = costBenefit
        this.destinations = destinations
        return { overview, workshops, machineLines, coils, costBenefit, destinations }
      } catch (error) {
        this.lastError = error?.message || '加载工厂数据失败'
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})
