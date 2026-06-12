import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ACTIVE_WORKSHOP_NAMES,
  filterActiveWorkshopRows,
  isActiveWorkshopName,
  normalizeWorkshopName,
} from '../src/utils/activeWorkshops.js'
import { buildDailyWipRows, buildDailyWorkshopRows } from '../src/utils/manageDailyReportSurface.js'
import { buildFillLedgerRows } from '../src/utils/manageFillDetailsAudit.js'
import { buildLiveMachineMatrix, buildLiveProcessFlowItems } from '../src/utils/liveDashboardPhase2.js'

const EXPECTED_ACTIVE_WORKSHOPS = [
  '铸锭',
  '铸二',
  '铸三',
  '热轧',
  '淬火车间',
  '精整',
  '拉矫',
  '园区剪切',
  '新厂在线',
  '园区在线',
  '冷轧1650',
  '冷轧1850',
  '冷轧2050',
]

test('active workshop canonical list matches the thirteen business workshops', () => {
  assert.deepEqual(ACTIVE_WORKSHOP_NAMES, EXPECTED_ACTIVE_WORKSHOPS)
})

test('workshop normalization maps common historical names to the thirteen active names', () => {
  assert.equal(normalizeWorkshopName('铸锭车间'), '铸锭')
  assert.equal(normalizeWorkshopName('铸轧二'), '铸二')
  assert.equal(normalizeWorkshopName('铸轧三'), '铸三')
  assert.equal(normalizeWorkshopName('铸二车间'), '铸二')
  assert.equal(normalizeWorkshopName('铸三车间'), '铸三')
  assert.equal(normalizeWorkshopName('热轧车间'), '热轧')
  assert.equal(normalizeWorkshopName('园区淬火'), '淬火车间')
  assert.equal(normalizeWorkshopName('精整车间'), '精整')
  assert.equal(normalizeWorkshopName('园区剪切车间'), '园区剪切')
  assert.equal(normalizeWorkshopName('新厂在线退火'), '新厂在线')
  assert.equal(normalizeWorkshopName('园区在线车间'), '园区在线')
  assert.equal(normalizeWorkshopName('1650冷轧'), '冷轧1650')
  assert.equal(normalizeWorkshopName('1650冷轧车间'), '冷轧1650')
  assert.equal(normalizeWorkshopName('1850冷轧'), '冷轧1850')
  assert.equal(normalizeWorkshopName('1850冷轧车间'), '冷轧1850')
  assert.equal(normalizeWorkshopName('2050冷轧'), '冷轧2050')
  assert.equal(normalizeWorkshopName('2050冷轧车间'), '冷轧2050')
})

test('active workshop filter removes retired workshops and keeps canonical rows', () => {
  const rows = filterActiveWorkshopRows([
    { workshop: '铸锭车间', daily_output: 10 },
    { workshop: '冷轧三车间', daily_output: 99 },
    { workshop: '二分厂精整车间', daily_output: 88 },
    { workshop_name: '园区淬火', daily_output: 8 },
    { workshop_name: '园区在线退火', daily_output: 12 },
    { workshop_name: '陌生车间', daily_output: 1 },
    { workshop_name: '热轧车间', is_active: false, daily_output: 7 },
  ])

  assert.deepEqual(rows.map((row) => row.workshop || row.workshop_name), ['铸锭', '淬火车间', '园区在线'])
  assert.equal(isActiveWorkshopName('冷轧三车间'), false)
  assert.equal(isActiveWorkshopName('淬火'), true)
  assert.equal(isActiveWorkshopName('冷轧2050'), true)
})

test('daily report rows use the canonical thirteen-workshop surface', () => {
  const workshopRows = buildDailyWorkshopRows([
    { workshop: '铸锭车间', daily_output: 10 },
    { workshop: '园区在线退火', daily_output: 12 },
    { workshop: '冷轧三车间', daily_output: 99 },
    { workshop: '陌生车间', daily_output: 1 },
  ])
  const wipRows = buildDailyWipRows([
    { workshop: '1650冷轧车间', total_weight: 6, coil_count: 2 },
    { workshop: '二分厂精整车间', total_weight: 88, coil_count: 8 },
    { workshop: '旧车间', total_weight: 1, coil_count: 1 },
  ])

  assert.deepEqual(workshopRows.map((row) => row.workshop), ['园区在线', '铸锭'])
  assert.deepEqual(wipRows.map((row) => row.title), ['冷轧1650'])
})

test('live dashboard matrix and process flow use canonical workshop names', () => {
  const workshops = [
    {
      workshop_id: 1,
      workshop_name: '2050冷轧车间',
      machines: [{ machine_id: 11, machine_name: '2050轧机', day_total: { output: 8 } }],
    },
    {
      workshop_id: 2,
      workshop_name: '冷轧三车间',
      machines: [{ machine_id: 12, machine_name: '旧轧机', day_total: { output: 99 } }],
    },
    {
      workshop_id: 3,
      workshop_name: '陌生车间',
      machines: [{ machine_id: 13, machine_name: '未知机列', day_total: { output: 1 } }],
    },
  ]

  const matrix = buildLiveMachineMatrix(workshops)
  const flow = buildLiveProcessFlowItems({ workshops })
  const coldRolling = flow.find((row) => row.key === 'cold-rolling')

  assert.deepEqual(matrix.workshops.map((row) => row.workshopName), ['冷轧2050'])
  assert.deepEqual(coldRolling.workshopNames, ['冷轧2050'])
  assert.equal(coldRolling.valueText, '8 吨')
})

test('fill details keeps manual rows only and normalizes active workshop names', () => {
  const rows = buildFillLedgerRows([
    { id: 1, source_type: 'owner_daily', workshop_name: '园区剪切车间', responsible_name: '张三' },
    { id: 2, source_type: 'mes_projection', workshop_name: '精整车间', responsible_name: 'MES' },
    { id: 3, source_type: 'owner_daily', workshop_name: '二分厂精整车间', responsible_name: '旧角色' },
    { id: 4, source_type: 'owner_daily', workshop_name: '陌生车间', responsible_name: '未知' },
  ])

  assert.deepEqual(rows.map((row) => row.workshopName), ['园区剪切'])
  assert.equal(rows[0].machineName, '内勤岗')
})
