import test from 'node:test'
import assert from 'node:assert/strict'
import { shapeEnergyTrend } from '../src/components/manage/_costPanel.js'

test('energy trend preserves missing production and avoids calculating a ratio without a denominator', () => {
  const [point] = shapeEnergyTrend([{ date: '2026-09-13', output: null, energy: 1000 }])
  assert.equal(point.tons, null)
  assert.equal(point.energy, 1000)
  assert.equal(point.energyPerTon, null)
})
