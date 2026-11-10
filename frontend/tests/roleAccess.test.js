import test from 'node:test'
import assert from 'node:assert/strict'

const memoryStorage = { getItem: () => null, setItem() {}, removeItem() {} }
globalThis.sessionStorage ??= memoryStorage
globalThis.localStorage ??= memoryStorage

const { accessForUser, summarizeRoles } = await import('../src/utils/role-access.js')

const base = { is_active: true, is_mobile_user: false, is_reviewer: false, is_manager: false }

test('admin sees every left-nav group plus fill entry', () => {
  const access = accessForUser({ ...base, role: 'admin' })

  assert.equal(access.fill, true)
  assert.deepEqual(access.groups.map((group) => group.label), ['主线', '业务', '配置', '权限', '工具', '其他'])
  assert.ok(access.groups.find((group) => group.label === '权限').titles.includes('用户与角色'))
})

test('manager flag opens review pages but no admin groups', () => {
  const access = accessForUser({ ...base, role: 'planning_owner', is_manager: true })

  assert.equal(access.fill, false)
  assert.deepEqual(access.groups.map((group) => group.label), ['主线', '业务', '工具', '其他'])
})

test('mobile-only operator gets fill entry and no desktop pages', () => {
  const access = accessForUser({ ...base, role: 'machine_operator', is_mobile_user: true })

  assert.equal(access.fill, true)
  assert.equal(access.pageCount, 0)
})

test('workshop director is limited to the own-workshop group', () => {
  const access = accessForUser({ ...base, role: 'workshop_director' })

  assert.deepEqual(access.groups.map((group) => group.label), ['本车间'])
})

test('role summary counts accounts and marks roles whose accounts differ', () => {
  const rows = summarizeRoles([
    { ...base, role: 'machine_operator', is_mobile_user: true },
    { ...base, role: 'machine_operator', is_mobile_user: true },
    { ...base, role: 'machine_operator', is_mobile_user: true, is_active: false },
    { ...base, role: 'energy_stat', is_mobile_user: true },
    { ...base, role: 'energy_stat', is_manager: true }
  ])

  const operator = rows.find((row) => row.role === 'machine_operator')
  assert.equal(operator.total, 3)
  assert.equal(operator.active, 2)
  assert.equal(operator.fill, true)
  assert.equal(operator.pageCount, 0)
  assert.equal(operator.variants.length, 1)
  assert.equal(operator.variants[0].count, 2)

  const energy = rows.find((row) => row.role === 'energy_stat')
  assert.equal(energy.fill, 'mixed')
  assert.equal(energy.pageCount, 'mixed')
  assert.equal(energy.variants.length, 2)
})
