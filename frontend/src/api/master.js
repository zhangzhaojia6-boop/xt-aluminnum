import { api } from './index.js'

function unwrapItems(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.items)) return payload.items
  return []
}

function unwrapPage(payload) {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length,
      skip: 0,
      limit: payload.length
    }
  }
  return {
    items: Array.isArray(payload?.items) ? payload.items : [],
    total: Number(payload?.total || 0),
    skip: Number(payload?.skip || 0),
    limit: Number(payload?.limit || 0)
  }
}

const crud = (resource) => ({
  list: async (params = {}) => unwrapItems((await api.get(`/master/${resource}`, { params })).data),
  listPage: async (params = {}) => unwrapPage((await api.get(`/master/${resource}`, { params })).data),
  create: async (payload) => (await api.post(`/master/${resource}`, payload)).data,
  update: async (id, payload) => (await api.put(`/master/${resource}/${id}`, payload)).data,
  patch: async (id, payload) => (await api.patch(`/master/${resource}/${id}`, payload)).data,
  remove: async (id) => (await api.delete(`/master/${resource}/${id}`)).data,
  detail: async (id) => (await api.get(`/master/${resource}/${id}`)).data
})

export const workshopApi = crud('workshops')
export const teamApi = crud('teams')
export const employeeApi = crud('employees')
export const equipmentApi = crud('equipment')
export const shiftConfigApi = crud('shift-configs')

export async function fetchWorkshops(params = {}) {
  return workshopApi.list(params)
}

export async function fetchWorkshopsPage(params = {}) {
  return workshopApi.listPage(params)
}

export const listWorkshops = fetchWorkshops

export async function createWorkshop(payload) {
  return workshopApi.create(payload)
}

export async function updateWorkshop(id, payload) {
  return workshopApi.update(id, payload)
}

export async function deleteWorkshop(id) {
  return workshopApi.remove(id)
}

export async function fetchTeams(params = {}) {
  return teamApi.list(params)
}

export async function fetchTeamsPage(params = {}) {
  return teamApi.listPage(params)
}

export const listTeams = fetchTeams

export async function createTeam(payload) {
  return teamApi.create(payload)
}

export async function updateTeam(id, payload) {
  return teamApi.update(id, payload)
}

export async function deleteTeam(id) {
  return teamApi.remove(id)
}

export async function fetchEmployees(params = {}) {
  return employeeApi.list(params)
}

export async function fetchEmployeesPage(params = {}) {
  return employeeApi.listPage(params)
}

export const listEmployees = fetchEmployees

export async function createEmployee(payload) {
  return employeeApi.create(payload)
}

export async function updateEmployee(id, payload) {
  return employeeApi.update(id, payload)
}

export async function deleteEmployee(id) {
  return employeeApi.remove(id)
}

export async function fetchEquipment(params = {}) {
  return equipmentApi.list(params)
}

export async function fetchEquipmentPage(params = {}) {
  return equipmentApi.listPage(params)
}

export async function fetchEquipmentDetail(id) {
  return equipmentApi.detail(id)
}

export const listEquipment = fetchEquipment

export async function updateEquipment(id, payload) {
  return equipmentApi.patch(id, payload)
}

export async function createMachineWithAccount(payload) {
  const { data } = await api.post('/master/equipment/create-with-account', payload)
  return data
}

export async function resetEquipmentPin(id) {
  const { data } = await api.post(`/master/equipment/${id}/reset-pin`)
  return data
}

export async function toggleEquipmentStatus(id, operationalStatus) {
  const { data } = await api.post(`/master/equipment/${id}/toggle-status`, {
    operational_status: operationalStatus
  })
  return data
}

export async function fetchShiftConfigs(params = {}) {
  return shiftConfigApi.list(params)
}

export async function fetchShiftConfigsPage(params = {}) {
  return shiftConfigApi.listPage(params)
}

export const listShiftConfigs = fetchShiftConfigs

export async function createShiftConfig(payload) {
  return shiftConfigApi.create(payload)
}

export async function updateShiftConfig(id, payload) {
  return shiftConfigApi.update(id, payload)
}

export async function deleteShiftConfig(id) {
  return shiftConfigApi.remove(id)
}

export async function fetchAliasMappings(params = {}) {
  return unwrapItems((await api.get('/master/aliases', { params })).data)
}

export async function fetchAliasMappingsPage(params = {}) {
  return unwrapPage((await api.get('/master/aliases', { params })).data)
}

export async function createAliasMapping(payload) {
  const { data } = await api.post('/master/aliases', payload)
  return data
}

export async function updateAliasMapping(id, payload) {
  const { data } = await api.put(`/master/aliases/${id}`, payload)
  return data
}

export async function deleteAliasMapping(id) {
  const { data } = await api.delete(`/master/aliases/${id}`)
  return data
}

export async function fetchWorkshopTemplateConfig(templateKey) {
  const { data } = await api.get(`/master/workshop-templates/${templateKey}`)
  return data
}

export async function updateWorkshopTemplateConfig(templateKey, payload) {
  const { data } = await api.put(`/master/workshop-templates/${templateKey}`, payload)
  return data
}
