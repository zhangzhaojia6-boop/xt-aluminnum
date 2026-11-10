import test from 'node:test'
import assert from 'node:assert/strict'

import { buildFactoryModel, FACTORY_BLOCKS, SITE, PLAN_SIZE } from '../src/utils/factory-layout.js'
import { buildingParts, toWorld } from '../src/utils/plant-parts.js'

function model(rows) {
  return Object.fromEntries(buildFactoryModel(rows).blocks.map((block) => [block.key, block]))
}

test('building shells have a fixed height no matter how many tons', () => {
  const blocks = model([
    { workshop_name: '铸轧二', total_output: 500 },
    { workshop_name: '铸轧三', total_output: 5 }
  ])
  assert.equal(buildingParts(blocks.ZR2).wall.h, buildingParts(blocks.ZR3).wall.h)
  assert.equal(buildingParts(blocks.ZR2).wall.h, buildingParts(blocks.RZ).wall.h)
})

test('only workshops with data get a roof bar, taller for more tons', () => {
  const blocks = model([
    { workshop_name: '铸轧二', total_output: 500 },
    { workshop_name: '铸轧三', total_output: 50 },
    { workshop_name: '热轧', total_output: null }
  ])
  const big = buildingParts(blocks.ZR2).bar
  const small = buildingParts(blocks.ZR3).bar
  assert.ok(big && small)
  assert.ok(big.h > small.h)
  assert.equal(buildingParts(blocks.RZ).bar, null)
  assert.equal(buildingParts(blocks.office).bar, null)
})

test('bars stand on the roof ridge and labels sit above them', () => {
  const blocks = model([{ workshop_name: '精整车间', total_output: 120 }])
  const parts = buildingParts(blocks.JZ)
  assert.equal(parts.bar.y, parts.wall.h + parts.roof.rise)
  assert.ok(parts.labelY > parts.bar.y + parts.bar.h)
})

test('the ridge runs along the long side and gets ventilators and a skylight', () => {
  const blocks = model([])
  const long = buildingParts(blocks.ZR2)
  assert.equal(long.alongX, true)
  assert.ok(long.skylight.w > long.skylight.d)
  assert.ok(long.vents.length >= 5)
  const deep = buildingParts(blocks.LZ1650)
  assert.equal(deep.alongX, false)
  assert.ok(deep.skylight.d > deep.skylight.w)
  assert.equal(buildingParts(blocks.office).vents.length, 0)
  assert.equal(buildingParts(blocks.office).skylight, null)
})

test('annex buildings are lower than workshops', () => {
  const blocks = model([])
  assert.ok(buildingParts(blocks.office).wall.h < buildingParts(blocks.ZR2).wall.h)
})

test('roads, gates and parking stay inside the fence and never cover a building', () => {
  const inside = (r, f) => r.x >= f.x && r.y >= f.y && r.x + r.w <= f.x + f.w && r.y + r.h <= f.y + f.h
  const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  assert.ok(SITE.fence.x >= 0 && SITE.fence.x + SITE.fence.w <= PLAN_SIZE.width)
  for (const rect of [...SITE.roads, ...SITE.gates, ...SITE.parking]) {
    assert.ok(inside(rect, SITE.fence), JSON.stringify(rect))
    for (const block of FACTORY_BLOCKS) assert.equal(overlap(rect, block), false, `${JSON.stringify(rect)} covers ${block.key}`)
  }
})

test('plan coordinates map to centred world coordinates', () => {
  const world = toWorld({ x: 0, y: 0, w: PLAN_SIZE.width, h: PLAN_SIZE.height })
  assert.equal(world.cx, 0)
  assert.equal(world.cz, 0)
})
