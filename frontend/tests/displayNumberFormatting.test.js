import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { compareShiftLabels, formatNumber, formatRoleLabel, formatShiftLabel, shiftOrderIndex } from '../src/utils/display.js'

test('formatNumber hides trailing decimal zeros on management and entry values', () => {
  assert.equal(formatNumber(12), '12')
  assert.equal(formatNumber(12.0), '12')
  assert.equal(formatNumber(12.5), '12.5')
  assert.equal(formatNumber(12.345), '12.35')
})

test('formatShiftLabel normalizes historical shift names for display', () => {
  assert.equal(formatShiftLabel('A'), '长白班')
  assert.equal(formatShiftLabel('D'), '长白班')
  assert.equal(formatShiftLabel('白班'), '长白班')
  assert.equal(formatShiftLabel('B'), '小夜班')
  assert.equal(formatShiftLabel('E'), '小夜班')
  assert.equal(formatShiftLabel('中班'), '小夜班')
  assert.equal(formatShiftLabel('C'), '大夜班')
  assert.equal(formatShiftLabel('N'), '大夜班')
  assert.equal(formatShiftLabel('夜班'), '大夜班')
  assert.equal(formatShiftLabel('大夜'), '大夜班')
})

test('shift display order starts at 07:30 production day', () => {
  assert.equal(shiftOrderIndex('长白班'), 0)
  assert.equal(shiftOrderIndex('小夜'), 1)
  assert.equal(shiftOrderIndex('大夜'), 2)
  assert.deepEqual(['大夜', '长白班', '小夜班'].sort(compareShiftLabels), ['长白班', '小夜班', '大夜'])
})

test('management energy and legacy live surfaces use canonical shift labels', () => {
  const energySource = readFileSync(new URL('../src/views/energy/EnergyCenter.vue', import.meta.url), 'utf8')
  const legacyLiveSource = readFileSync(new URL('../src/views/reports/LiveDashboard.vue', import.meta.url), 'utf8')

  assert.match(energySource, /formatShiftLabel\(row\.shift_code, '-'\)/)
  assert.match(legacyLiveSource, /formatShiftLabel\(shift\.shift_name, '-'\)/)
  assert.match(legacyLiveSource, /formatShiftLabel\(activeCell\.shift_name, '-'\)/)
})

test('role labels do not mark active business roles as disabled', () => {
  assert.equal(formatRoleLabel('factory_director'), '厂长')
  assert.equal(formatRoleLabel('manager'), '车间管理')
  assert.equal(formatRoleLabel('qc'), '质检内勤')
  assert.equal(formatRoleLabel('utility_manager'), '全厂总电工(兼容)')
  assert.equal(formatRoleLabel('shift_leader'), '已取消班长(移动端)')
})
