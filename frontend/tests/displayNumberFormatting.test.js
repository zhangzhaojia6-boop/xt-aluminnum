import test from 'node:test'
import assert from 'node:assert/strict'

import { formatNumber, formatShiftLabel } from '../src/utils/display.js'

test('formatNumber hides trailing decimal zeros on management and entry values', () => {
  assert.equal(formatNumber(12), '12')
  assert.equal(formatNumber(12.0), '12')
  assert.equal(formatNumber(12.5), '12.5')
  assert.equal(formatNumber(12.345), '12.35')
})

test('formatShiftLabel normalizes historical shift names for display', () => {
  assert.equal(formatShiftLabel('A'), '长白班')
  assert.equal(formatShiftLabel('白班'), '长白班')
  assert.equal(formatShiftLabel('B'), '小夜班')
  assert.equal(formatShiftLabel('中班'), '小夜班')
  assert.equal(formatShiftLabel('C'), '大夜班')
  assert.equal(formatShiftLabel('夜班'), '大夜班')
  assert.equal(formatShiftLabel('大夜'), '大夜班')
})
