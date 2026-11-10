import test from 'node:test'
import assert from 'node:assert/strict'

import { FACTORY_BLOCKS, PLAN_SIZE, buildFactoryModel, formatTons } from '../src/utils/factory-layout.js'

test('every block sits inside the plan and blocks do not overlap', () => {
  for (const block of FACTORY_BLOCKS) {
    assert.ok(block.x >= 0 && block.x + block.w <= PLAN_SIZE.width, block.key)
    assert.ok(block.y >= 0 && block.y + block.h <= PLAN_SIZE.height, block.key)
  }
  for (const a of FACTORY_BLOCKS) {
    for (const b of FACTORY_BLOCKS) {
      if (a === b) continue
      const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
      assert.equal(overlap, false, `${a.key} overlaps ${b.key}`)
    }
  }
})

test('workshop output maps onto blocks by official name; missing data stays flat, not zero', () => {
  const { blocks, offMap } = buildFactoryModel([
    { workshop_id: 2, workshop_name: '铸轧二', total_output: 120 },
    { workshop_id: 3, workshop_name: '铸轧三', total_output: 60 },
    { workshop_id: 4, workshop_name: '热轧', total_output: null },
    { workshop_id: 10, workshop_name: '剪切车间', total_output: 33.25 }
  ])
  const byKey = Object.fromEntries(blocks.map((block) => [block.key, block]))

  assert.equal(byKey.ZR2.workshopId, 2)
  assert.equal(byKey.ZR2.hasData, true)
  assert.ok(byKey.ZR2.height > byKey.ZR3.height)
  assert.equal(byKey.RZ.hasData, false)
  assert.equal(byKey.RZ.tons, null)
  assert.ok(byKey.RZ.height < byKey.ZR3.height)
  assert.equal(byKey.LZ2050.hasData, false)
  assert.equal(byKey.office.isWorkshop, false)
  assert.deepEqual(offMap, [{ name: '剪切车间', workshopId: 10, tons: 33.25 }])
})

test('heights scale within each process group, not across groups', () => {
  const { blocks } = buildFactoryModel([
    { workshop_name: '铸轧二', total_output: 100 },
    { workshop_name: '2050冷轧', total_output: 10 }
  ])
  const byKey = Object.fromEntries(blocks.map((block) => [block.key, block]))
  assert.equal(byKey.ZR2.height, byKey.LZ2050.height)
})

test('tons format keeps missing as a dash', () => {
  assert.equal(formatTons(null), '—')
  assert.equal(formatTons(0), '0')
  assert.equal(formatTons(1234.56), '1,234.6')
})
