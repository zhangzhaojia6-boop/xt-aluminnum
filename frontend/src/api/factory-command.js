import { api } from './index'

export async function fetchFactoryCommandOverview() {
  const { data } = await api.get('/factory-command/overview')
  return data
}

export async function fetchFactoryCommandWorkshops() {
  const { data } = await api.get('/factory-command/workshops')
  return data
}

export async function fetchFactoryCommandMachineLines() {
  const { data } = await api.get('/factory-command/machine-lines')
  return data
}

export async function fetchFactoryCommandCoils(params = {}) {
  const { data } = await api.get('/factory-command/coils', { params })
  return data
}

export async function fetchFactoryCommandCoilFlow(coilKey) {
  const { data } = await api.get(`/factory-command/coils/${encodeURIComponent(coilKey)}/flow`)
  return data
}

export async function fetchFactoryCommandCostBenefit() {
  const { data } = await api.get('/factory-command/cost-benefit')
  return data
}

export async function fetchFactoryCommandDestinations() {
  const { data } = await api.get('/factory-command/destinations')
  return data
}

export async function askFactoryCommandAi(payload = {}) {
  const { data } = await api.post('/ai/assistant/ask', payload)
  return data
}
