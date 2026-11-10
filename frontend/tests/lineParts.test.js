import test from 'node:test'
import assert from 'node:assert/strict'

import { STATION_GAP, buildLineParts } from '../src/utils/line-parts.js'

const items = [
  { key: 'casting', stage: '铸轧', output: 10.71, valueText: '10.71 吨' },
  { key: 'hot-rolling', stage: '热轧', output: null, valueText: '待同步' },
  { key: 'cold-rolling', stage: '冷轧', output: 115.42, valueText: '115.42 吨' },
  { key: 'annealing', stage: '退火', output: null, valueText: '待同步' },
  { key: 'finishing', stage: '精整', output: 133.1, valueText: '133.1 吨' },
  { key: 'packaging', stage: '包装入库', output: 68.72, valueText: '68.72 吨' }
]

test('stations line up left to right, centred, one gap apart', () => {
  const { stations } = buildLineParts(items)
  assert.deepEqual(stations.map((s) => s.key), items.map((i) => i.key))
  for (let i = 1; i < stations.length; i++) assert.equal(stations[i].x - stations[i - 1].x, STATION_GAP)
  assert.equal(stations[0].x + stations.at(-1).x, 0)
})

test('each process gets recognisable equipment', () => {
  const { parts } = buildLineParts(items)
  const near = (x) => parts.filter((p) => Math.abs(p.cx - x) < STATION_GAP / 2)
  const { stations } = buildLineParts(items)
  const byKey = Object.fromEntries(stations.map((s) => [s.key, near(s.x)]))
  assert.ok(byKey.casting.some((p) => p.mat === 'furnace'))
  assert.ok(byKey.casting.filter((p) => p.mat === 'roll').length >= 2)
  assert.equal(byKey['hot-rolling'].filter((p) => p.mat === 'roll').length, 4)
  assert.equal(byKey['cold-rolling'].filter((p) => p.mat === 'roll').length, 8)
  assert.ok(byKey.annealing.some((p) => p.mat === 'furnace'))
  assert.ok(byKey.finishing.some((p) => p.mat === 'table'))
  assert.ok(byKey.packaging.filter((p) => p.mat === 'coil').length >= 4)
})

test('bars follow real tonnage; missing output gets no bar, never zero', () => {
  const { stations } = buildLineParts(items)
  const byKey = Object.fromEntries(stations.map((s) => [s.key, s]))
  assert.equal(byKey['hot-rolling'].bar, null)
  assert.equal(byKey.annealing.bar, null)
  assert.ok(byKey.finishing.bar.h > byKey['cold-rolling'].bar.h)
  assert.ok(byKey['cold-rolling'].bar.h > byKey.casting.bar.h)
  assert.equal(byKey.annealing.valueText, '待同步')
})

test('a conveyor with rollers spans the whole line and carries the moving coil path', () => {
  const { conveyor, rollers, coilPath, stations } = buildLineParts(items)
  assert.ok(conveyor.w > stations.at(-1).x - stations[0].x)
  assert.ok(rollers.length > 40)
  assert.ok(coilPath.from < stations[0].x && coilPath.to > stations.at(-1).x)
})

test('the coil only moves when some station has data', () => {
  assert.equal(buildLineParts(items).hasAnyData, true)
  assert.equal(buildLineParts(items.map((i) => ({ ...i, output: null }))).hasAnyData, false)
  assert.equal(buildLineParts([]).conveyor, null)
})
