import test from 'node:test'
import assert from 'node:assert/strict'

import {
  destinationGroupLabel,
  formatMachineLineMetric,
  freshnessLabel,
  sourceLabel
} from '../src/utils/factoryCommandFormatters.js'

test('freshness label maps factory command sync states', () => {
  assert.equal(freshnessLabel('fresh'), '实时')
  assert.equal(freshnessLabel('stale'), '滞后')
  assert.equal(freshnessLabel('offline_or_blocked'), '离线/阻塞')
})

test('source label maps factory command sources', () => {
  assert.equal(sourceLabel('mes_projection'), 'MES 投影')
  assert.equal(sourceLabel('local_entry'), '本地填报')
  assert.equal(sourceLabel('mixed'), '混合来源')
})

test('machine-line formatter preserves operating estimates and missing data', () => {
  const row = formatMachineLineMetric({
    line_code: '冷轧:01',
    active_tons: 12.3456,
    finished_tons: 8.2,
    stalled_count: 2,
    cost_estimate: { estimated_cost: 1200, missing_data: ['energy'] },
    margin_estimate: { estimated_gross_margin: 360 }
  })

  assert.equal(row.lineCode, '冷轧:01')
  assert.equal(row.activeTons, 12.35)
  assert.equal(row.finishedTons, 8.2)
  assert.equal(row.stalledCount, 2)
  assert.equal(row.estimatedCost, 1200)
  assert.equal(row.estimatedGrossMargin, 360)
  assert.deepEqual(row.missingCostData, ['energy'])
})

test('destination formatter maps operational groups', () => {
  assert.equal(destinationGroupLabel('in_progress'), '在制')
  assert.equal(destinationGroupLabel('finished_stock'), '成品库存')
  assert.equal(destinationGroupLabel('allocation'), '已分配')
  assert.equal(destinationGroupLabel('delivery'), '交付')
  assert.equal(destinationGroupLabel('unknown'), '未知')
})
