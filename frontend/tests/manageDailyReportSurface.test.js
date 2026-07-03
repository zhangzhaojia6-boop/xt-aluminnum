import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDailyComparisonCards,
  buildDailySettlementCards,
  buildFactClosureSurface,
  buildDailyWorkshopRows,
  buildDailyWipRows,
  MISSING_DAILY_VALUE
} from '../src/utils/manageDailyReportSurface.js'

test('daily settlement cards keep MES packaging output separate from plant inbound output', () => {
  const cards = buildDailySettlementCards({
    plant_output: {
      factory_feeding_daily_input: 88,
      daily_output: 81.25,
      finished_inbound_output: 73.6,
      monthly_output: 1234.5,
      energy_per_ton: 456.7,
      yield_rate: 83.64
    },
    workshop_output: [
      { workshop: '园区在线', daily_output: 40 },
      { workshop: '精整', daily_output: 50 }
    ],
    contracts: { daily_new: 12.5, unit: '吨' },
    energy: { total_cost: 3.2 },
    yield_rates: { daily: 95.6 }
  })

  assert.equal(cards.find((item) => item.key === 'feeding-input')?.value, '88')
  assert.equal(cards.find((item) => item.key === 'feeding-input')?.label, '投料量')
  assert.equal(cards.find((item) => item.key === 'feeding-input')?.sourceLabel, 'MES投料')
  assert.equal(cards.find((item) => item.key === 'plant-output')?.value, '81.25')
  assert.equal(cards.find((item) => item.key === 'plant-output')?.label, '包装产量')
  assert.equal(cards.find((item) => item.key === 'plant-output')?.sourceLabel, '包装工序')
  assert.equal(cards.find((item) => item.key === 'finished-inbound')?.value, '73.6')
  assert.equal(cards.find((item) => item.key === 'finished-inbound')?.label, '全厂入库产量')
  assert.equal(cards.find((item) => item.key === 'finished-inbound')?.sourceLabel, '成品入库')
  assert.equal(cards.find((item) => item.key === 'yield-rate')?.label, '全厂成品率')
  assert.equal(cards.find((item) => item.key === 'yield-rate')?.sourceLabel, '投料入库')
  assert.equal(cards.find((item) => item.key === 'yield-rate')?.value, '83.64')
  assert.equal(cards.find((item) => item.key === 'process-throughput')?.value, '90')
  assert.equal(cards.find((item) => item.key === 'contract-tonnage')?.unit, '吨')
})

test('daily values hide trailing zero decimals but keep useful precision', () => {
  const cards = buildDailySettlementCards({
    plant_output: { factory_feeding_daily_input: 90, daily_output: 81.2, finished_inbound_output: 80, energy_per_ton: 456 },
    workshop_output: [
      { workshop: '园区在线', daily_output: 40 },
      { workshop: '精整', daily_output: 50 },
    ],
    contracts: { daily_new: 12, unit: '吨' },
    energy: { total_cost: 3.2 },
    yield_rates: { daily: 95 },
  })

  assert.equal(cards.find((item) => item.key === 'feeding-input')?.value, '90')
  assert.equal(cards.find((item) => item.key === 'plant-output')?.value, '81.2')
  assert.equal(cards.find((item) => item.key === 'finished-inbound')?.value, '80')
  assert.equal(cards.find((item) => item.key === 'process-throughput')?.value, '90')
  assert.equal(cards.find((item) => item.key === 'contract-tonnage')?.value, '12')
  assert.equal(cards.find((item) => item.key === 'yield-rate')?.value, '95')
})

test('daily settlement cards never show fake zero for missing energy', () => {
  const cards = buildDailySettlementCards({
    plant_output: { daily_output: 0, monthly_output: 0 },
    contracts: { daily_new: null, unit: '吨' },
    energy: { data_available: false, total_electricity: 0, total_cost: null },
    yield_rates: { daily: null }
  })

  assert.equal(cards.find((item) => item.key === 'energy-per-ton')?.value, MISSING_DAILY_VALUE)
  assert.equal(cards.find((item) => item.key === 'finished-inbound')?.value, MISSING_DAILY_VALUE)
})

test('daily settlement cards do not fake process throughput when workshop rows are absent', () => {
  const cards = buildDailySettlementCards({
    plant_output: { daily_output: 10 },
    workshop_output: []
  })

  assert.equal(cards.find((item) => item.key === 'process-throughput')?.value, MISSING_DAILY_VALUE)
})

test('daily comparison cards show algorithm values first and owner filled values second', () => {
  const cards = buildDailyComparisonCards({
    energy: {
      total_electricity: 1200,
      owner_electricity: 1180,
      data_available: true
    },
    plant_output: {
      factory_feeding_daily_input: 100,
      finished_inbound_output: 86,
      yield_rate: 86,
    },
    yield_rates: {
      daily: 96.4,
      owner_daily: 95.1
    }
  })

  assert.deepEqual(
    cards.map((item) => [item.title, item.primaryLabel, item.compareLabel]),
    [
      ['算法能耗', '算法', '电工填报'],
      ['全厂成品率', '成品入库', '投料量']
    ]
  )
  assert.equal(cards[0].primaryValue, '1,200 度')
  assert.equal(cards[0].compareValue, '1,180 度')
  assert.equal(cards[1].primaryValue, '86 吨')
  assert.equal(cards[1].compareValue, '100 吨')
  assert.equal(cards[1].value, '86 %')
})

test('daily comparison cards accept electricity aliases shared with live and energy pages', () => {
  const cards = buildDailyComparisonCards({
    energy: {
      total_electricity: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards[0].primaryValue, '17,430 度')
  assert.equal(cards[0].compareValue, '17,020 度')
})

test('daily comparison cards do not display comprehensive total_energy as electricity', () => {
  const cards = buildDailyComparisonCards({
    energy: {
      total_energy: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards[0].primaryValue, MISSING_DAILY_VALUE)
  assert.equal(cards[0].compareValue, '17,020 度')
})

test('daily comparison cards treat algorithm_total_energy as available energy data', () => {
  const cards = buildDailyComparisonCards({
    energy: {
      algorithm_total_energy: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards[0].primaryValue, '17,430 度')
  assert.equal(cards[0].compareValue, '17,020 度')
  assert.equal(cards[0].tone, 'warning')
})

test('daily workshop rows filter cancelled workshops and keep throughput wording', () => {
  const rows = buildDailyWorkshopRows([
    { workshop: '园区在线', daily_output: 12, monthly_output: 90 },
    { workshop: '冷轧三车间', daily_output: 99, monthly_output: 99 },
    { workshop: '二分厂精整车间', daily_output: 88, monthly_output: 88 },
    { workshop: '旧车间', daily_output: 77, monthly_output: 77, is_active: false }
  ])

  assert.deepEqual(rows.map((row) => row.workshop), ['园区在线'])
  assert.equal(rows[0].dailyOutputText, '12 吨')
})

test('daily wip rows keep source positions and show daily snapshot reference', () => {
  const rows = buildDailyWipRows([
    {
      workshop: '园区在线',
      total_weight: 9.5,
      feeding_weight: 12.3,
      coil_count: 3,
      source_label: '外部 MES 当日快照参考',
    },
    { workshop: '新厂北线', total_weight: 122, coil_count: 0 },
    { workshop: '1650/2050冷轧', total_weight: 63.5, coil_count: 0 },
    { workshop: '冷轧三车间', total_weight: 99, coil_count: 9 },
    { workshop: '二分厂精整车间', total_weight: 88, coil_count: 8 },
    { workshop: '旧车间', total_weight: 77, coil_count: 7, is_active: false }
  ])

  assert.equal(rows.length, 3)
  assert.equal(rows[0].title, '园区在线')
  assert.equal(rows[0].weightText, '9.5 吨')
  assert.equal(rows[0].totalWeight, 9.5)
  assert.equal(rows[0].feedingText, '投料 12.3 吨')
  assert.equal(rows[0].sourceLabel, '外部 MES 当日快照参考')
  assert.deepEqual(rows.map((row) => row.title), ['园区在线', '新厂北线', '1650/2050冷轧'])
})

test('fact closure surface shows zero blocked count when critical facts are confirmed', () => {
  const surface = buildFactClosureSurface({
    status: 'confirmed',
    critical_fields: [
      {
        field: 'total_output_daily',
        status: 'confirmed',
        source: '钉钉群日报',
        action: '已完成',
        trace_id: 'trace-1',
      },
      {
        field: 'finished_inbound_daily',
        status: 'confirmed',
        source: '成品入库单',
        action: '已完成',
        trace_id: 'trace-2',
      },
    ],
  })

  assert.equal(surface.status, 'confirmed')
  assert.equal(surface.blockedCount, 0)
  assert.deepEqual(surface.criticalFields, [
    {
      key: 'total_output_daily',
      status: 'confirmed',
      source: '钉钉群日报',
      action: '已完成',
      traceId: 'trace-1',
    },
    {
      key: 'finished_inbound_daily',
      status: 'confirmed',
      source: '成品入库单',
      action: '已完成',
      traceId: 'trace-2',
    },
  ])
})

test('fact closure surface counts missing and mismatch facts as blocked', () => {
  const surface = buildFactClosureSurface({
    status: 'conflict',
    critical_fields: [
      {
        field: 'total_output_daily',
        status: 'missing',
        action: '追补日报',
      },
      {
        field: 'finished_inbound_daily',
        status: 'mismatch',
        source: 'MES/WMS 对比',
        trace_id: 'trace-3',
      },
      {
        field: 'daily_yield_rate',
        status: 'confirmed',
        source: '日报快照',
      },
    ],
  })

  assert.equal(surface.status, 'conflict')
  assert.equal(surface.blockedCount, 2)
  assert.deepEqual(surface.criticalFields, [
    {
      key: 'total_output_daily',
      status: 'missing',
      source: '暂无可信来源',
      action: '追补日报',
      traceId: '',
    },
    {
      key: 'finished_inbound_daily',
      status: 'mismatch',
      source: 'MES/WMS 对比',
      action: '等待鑫泰铝业智能大脑追踪',
      traceId: 'trace-3',
    },
    {
      key: 'daily_yield_rate',
      status: 'confirmed',
      source: '日报快照',
      action: '等待鑫泰铝业智能大脑追踪',
      traceId: '',
    },
  ])
})

test('fact closure surface does not introduce helper marketing text fields', () => {
  const surface = buildFactClosureSurface({
    critical_fields: [{ field: 'total_output_daily', status: 'missing' }],
  })

  assert.equal(surface.criticalFields[0].source, '暂无可信来源')
  assert.deepEqual(
    Object.keys(surface).sort(),
    ['blockedCount', 'criticalFields', 'status']
  )
  assert.deepEqual(
    Object.keys(surface.criticalFields[0]).sort(),
    ['action', 'key', 'source', 'status', 'traceId']
  )
  for (const forbiddenKey of ['description', 'explanation', 'helperText', 'tooltip', 'note', 'rationale']) {
    assert.equal(forbiddenKey in surface, false)
    assert.equal(forbiddenKey in surface.criticalFields[0], false)
  }
})

test('fact closure surface falls back cleanly when fact closure payload is absent or malformed', () => {
  assert.deepEqual(buildFactClosureSurface(), {
    status: 'unknown',
    blockedCount: 0,
    criticalFields: [],
  })

  assert.deepEqual(buildFactClosureSurface(null), {
    status: 'unknown',
    blockedCount: 0,
    criticalFields: [],
  })

  assert.deepEqual(buildFactClosureSurface({
    status: 'candidate',
    critical_fields: null,
  }), {
    status: 'candidate',
    blockedCount: 0,
    criticalFields: [],
  })

  assert.deepEqual(buildFactClosureSurface({
    status: 'conflict',
    critical_fields: 'not-an-array',
  }), {
    status: 'conflict',
    blockedCount: 0,
    criticalFields: [],
  })
})

test('fact closure surface ignores null field entries instead of crashing', () => {
  const surface = buildFactClosureSurface({
    status: 'missing',
    critical_fields: [null],
  })

  assert.deepEqual(surface, {
    status: 'missing',
    blockedCount: 0,
    criticalFields: [],
  })
})
