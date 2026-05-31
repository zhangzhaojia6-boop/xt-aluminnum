import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDailyComparisonCards,
  buildDailySettlementCards,
  buildDailyWorkshopRows,
  buildDailyWipRows,
  MISSING_DAILY_VALUE
} from '../src/utils/manageDailyReportSurface.js'

test('daily settlement cards keep plant inbound output separate from process throughput', () => {
  const cards = buildDailySettlementCards({
    plant_output: {
      daily_output: 81.25,
      monthly_output: 1234.5,
      energy_per_ton: 456.7
    },
    workshop_output: [
      { workshop: '退火一车间', daily_output: 40 },
      { workshop: '包装车间', daily_output: 50 }
    ],
    contracts: { daily_new: 12.5, unit: '吨' },
    energy: { total_cost: 3.2 },
    yield_rates: { daily: 95.6 }
  })

  assert.equal(cards.find((item) => item.key === 'plant-output')?.value, '81.25')
  assert.equal(cards.find((item) => item.key === 'process-throughput')?.value, '90')
  assert.equal(cards.find((item) => item.key === 'contract-tonnage')?.unit, '吨')
})

test('daily values hide trailing zero decimals but keep useful precision', () => {
  const cards = buildDailySettlementCards({
    plant_output: { daily_output: 81.2, energy_per_ton: 456 },
    workshop_output: [
      { workshop: '退火一车间', daily_output: 40 },
      { workshop: '包装车间', daily_output: 50 },
    ],
    contracts: { daily_new: 12, unit: '吨' },
    energy: { total_cost: 3.2 },
    yield_rates: { daily: 95 },
  })

  assert.equal(cards.find((item) => item.key === 'plant-output')?.value, '81.2')
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
  assert.equal(cards.find((item) => item.key === 'energy-cost')?.value, MISSING_DAILY_VALUE)
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
    yield_rates: {
      daily: 96.4,
      owner_daily: 95.1
    }
  })

  assert.deepEqual(
    cards.map((item) => [item.title, item.primaryLabel, item.compareLabel]),
    [
      ['算法能耗', '算法', '电工填报'],
      ['算法成品率', '算法', '内勤对照']
    ]
  )
  assert.equal(cards[0].primaryValue, '1,200 度')
  assert.equal(cards[0].compareValue, '1,180 度')
})

test('daily workshop rows filter cancelled workshops and keep throughput wording', () => {
  const rows = buildDailyWorkshopRows([
    { workshop: '退火一车间', daily_output: 12, monthly_output: 90 },
    { workshop: '冷轧三车间', daily_output: 99, monthly_output: 99 },
    { workshop: '二分厂精整车间', daily_output: 88, monthly_output: 88 },
    { workshop: '旧车间', daily_output: 77, monthly_output: 77, is_active: false }
  ])

  assert.deepEqual(rows.map((row) => row.workshop), ['退火一车间'])
  assert.equal(rows[0].dailyOutputText, '12 吨')
})

test('daily wip rows label external MES current inventory without day filtering copy', () => {
  const rows = buildDailyWipRows([
    { workshop: '退火一车间', total_weight: 9.5, coil_count: 3 },
    { workshop: '冷轧三车间', total_weight: 99, coil_count: 9 },
    { workshop: '二分厂精整车间', total_weight: 88, coil_count: 8 },
    { workshop: '旧车间', total_weight: 77, coil_count: 7, is_active: false }
  ])

  assert.equal(rows.length, 1)
  assert.equal(rows[0].title, '退火一车间')
  assert.equal(rows[0].weightText, '9.5 吨')
  assert.equal(rows[0].sourceLabel, '外部 MES 当前在制')
})
