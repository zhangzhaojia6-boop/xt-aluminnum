import test from 'node:test'
import assert from 'node:assert/strict'

import { LINE_PLAN, buildProcessLineBlocks } from '../src/utils/process-line-layout.js'

const items = [
  { key: 'casting', stage: '铸轧', output: 300, valueText: '300 吨' },
  { key: 'cold', stage: '冷轧', output: 150, valueText: '150 吨' },
  { key: 'finish', stage: '精整', output: null, valueText: '—' }
]

test('nodes line up left to right inside the plan with links between them', () => {
  const blocks = buildProcessLineBlocks(items)
  const nodes = blocks.filter((block) => block.isWorkshop)
  const links = blocks.filter((block) => !block.isWorkshop)

  assert.deepEqual(nodes.map((node) => node.key), ['casting', 'cold', 'finish'])
  assert.equal(links.length, 2)
  for (let i = 1; i < nodes.length; i++) assert.ok(nodes[i].x > nodes[i - 1].x + nodes[i - 1].w)
  for (const block of blocks) {
    assert.ok(block.x >= 0 && block.x + block.w <= LINE_PLAN.width, block.key)
    assert.ok(block.y >= 0 && block.y + block.h <= LINE_PLAN.height, block.key)
  }
})

test('height follows real tonnage and missing output stays flat, never zero', () => {
  const nodes = buildProcessLineBlocks(items).filter((block) => block.isWorkshop)
  const [casting, cold, finish] = nodes

  assert.ok(casting.height > cold.height)
  assert.equal(finish.hasData, false)
  assert.equal(finish.tons, null)
  assert.ok(finish.height < cold.height)
  assert.equal(finish.valueText, '—')
})

test('a line with no data at all is all flat', () => {
  const nodes = buildProcessLineBlocks(items.map((item) => ({ ...item, output: null }))).filter((block) => block.isWorkshop)
  assert.equal(new Set(nodes.map((node) => node.height)).size, 1)
  assert.equal(nodes.every((node) => !node.hasData), true)
})
