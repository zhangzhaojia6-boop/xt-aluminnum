import test from 'node:test'
import assert from 'node:assert/strict'
import {
  shapeTrendSeries,
  trendStats
} from '../src/components/manage/_outputTrend.js'

test('shapeTrendSeries tails to N days, maps date label, converts kg → t', () => {
  const raw = Array.from({ length: 30 }, (_, i) => ({
    date: `2026-05-${String(i + 1).padStart(2, '0')}`,
    output_weight: (i + 1) * 1000
  }))
  const out = shapeTrendSeries(raw, 14)
  assert.equal(out.length, 14)
  assert.equal(out[0].label, '05-17')
  assert.equal(out[13].label, '05-30')
  assert.equal(out[13].output, 30)
})

test('trendStats computes max/avg/last over valid points', () => {
  const series = [
    { output: 10 }, { output: 20 }, { output: 30 }
  ]
  const s = trendStats(series)
  assert.equal(s.max, 30)
  assert.equal(s.avg, 20)
  assert.equal(s.last, 30)
})

test('trendStats safe on empty', () => {
  const s = trendStats([])
  assert.equal(s.max, 0)
  assert.equal(s.avg, 0)
  assert.equal(s.last, 0)
})
