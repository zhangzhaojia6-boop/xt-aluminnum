import test from 'node:test'
import assert from 'node:assert/strict'

import { formatNumber } from '../src/utils/display.js'

test('formatNumber hides trailing decimal zeros on management and entry values', () => {
  assert.equal(formatNumber(12), '12')
  assert.equal(formatNumber(12.0), '12')
  assert.equal(formatNumber(12.5), '12.5')
  assert.equal(formatNumber(12.345), '12.35')
})
