import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const usersApiSource = readFileSync(new URL('../src/api/users.js', import.meta.url), 'utf8')
const userManagementSource = readFileSync(new URL('../src/views/master/UserManagement.vue', import.meta.url), 'utf8')

test('user api exposes dingtalk contact sync endpoint', () => {
  assert.match(usersApiSource, /syncDingtalkUsers/)
  assert.match(usersApiSource, /\/users\/sync-dingtalk/)
})

test('user management page exposes one-click dingtalk member sync', () => {
  assert.match(userManagementSource, /syncDingtalkUsers/)
  assert.match(userManagementSource, /同步钉钉成员/)
  assert.match(userManagementSource, /syncingDingtalk/)
})

test('user management page supports machine-line account binding', () => {
  assert.match(userManagementSource, /fetchEquipment/)
  assert.match(userManagementSource, /绑定机列/)
  assert.match(userManagementSource, /bound_machine_id/)
  assert.match(userManagementSource, /handleMachineChange/)
  assert.match(userManagementSource, /machine\.bound_user_id && machine\.bound_user_id !== editingId/)
})

test('user management page filters accounts by machine-line binding', () => {
  assert.match(userManagementSource, /绑定状态/)
  assert.match(userManagementSource, /machineBinding/)
  assert.match(userManagementSource, /boundMachineId/)
  assert.match(userManagementSource, /machine_binding/)
  assert.match(userManagementSource, /handleMachineBindingFilterChange/)
})

test('user management page can open directly on unbound account filter', () => {
  assert.match(userManagementSource, /useRoute/)
  assert.match(userManagementSource, /applyRouteFilters/)
  assert.match(userManagementSource, /route\.query\.machine_binding/)
  assert.match(userManagementSource, /route\.query\.bound_machine_id/)
})
