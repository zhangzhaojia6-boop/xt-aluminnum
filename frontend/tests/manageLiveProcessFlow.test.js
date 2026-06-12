import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildLiveProcessFlowItems } from '../src/utils/liveDashboardPhase2.js'
import { buildLiveStitchSurface } from '../src/utils/stitchManageSurface.js'

const pageSrc = readFileSync(
  new URL('../src/views/manage/live/LiveDashboardPage.vue', import.meta.url),
  'utf8',
)

test('buildLiveProcessFlowItems keeps a full process path without faking missing values as zero', () => {
  const rows = buildLiveProcessFlowItems({
    factory_total: {
      packaging_output: 88,
    },
    workshops: [
      {
        workshop_id: 1,
        workshop_name: '铸二',
        machines: [
          {
            machine_id: 11,
            machine_name: '1#机',
            machine_binding_status: 'bound',
            day_total: { input: 13, output: 12.35, scrap: 0.65 },
          },
          {
            machine_id: -101,
            machine_name: '未绑定机列 / 小夜班',
            machine_binding_status: 'unbound',
            day_total: { input: 5.5, output: 5, scrap: 0.5 },
          },
        ],
      },
      {
        workshop_id: 2,
        workshop_name: '冷轧三车间',
        status: 'removed',
        machines: [
          {
            machine_id: 21,
            machine_name: '已取消机列',
            day_total: { output: 999 },
          },
        ],
      },
      {
        workshop_id: 3,
        workshop_name: '2050冷轧车间',
        machines: [
          {
            machine_id: 31,
            machine_name: '2050轧机',
            day_total: {},
          },
        ],
      },
    ],
  })

  assert.deepEqual(rows.map((row) => row.stage), ['铸轧', '热轧', '冷轧', '退火', '精整', '包装入库'])

  const casting = rows.find((row) => row.key === 'casting')
  assert.equal(casting.output, 17.35)
  assert.equal(casting.valueText, '17.35 吨')
  assert.equal(casting.machineCount, 2)
  assert.equal(casting.pendingMachineCount, 1)
  assert.equal(casting.tone, 'warning')

  const coldRolling = rows.find((row) => row.key === 'cold-rolling')
  assert.equal(coldRolling.output, null)
  assert.equal(coldRolling.valueText, '待同步')
  assert.equal(coldRolling.machineCount, 1)
  assert.equal(coldRolling.hasTrustedOutput, false)

  const packaging = rows.find((row) => row.key === 'packaging')
  assert.equal(packaging.output, 88)
  assert.equal(packaging.valueText, '88 吨')
  assert.equal(packaging.source, 'MES包装')
})

test('manage live surface exposes process flow as a first-screen module', () => {
  const surface = buildLiveStitchSurface({
    aggregation: {
      factory_total: { packaging_output: 8 },
      workshops: [],
    },
    streamStatus: 'open',
  })

  assert.ok(surface.slotOrder.includes('processFlow'))
  assert.equal(surface.processFlow.length, 6)
  assert.match(pageSrc, /LiveProcessFlow/)
  assert.match(pageSrc, /processFlowItems/)
})

test('manage live bottom status separates IoT energy and electrician fill sources', () => {
  const surface = buildLiveStitchSurface({
    aggregation: {
      business_date: '2026-06-11',
      energy_summary: {
        algorithm_total_energy: 8840,
        algorithm_energy_per_ton: null,
        owner_total_electricity: 8700,
        primary_source_label: '物联网采集',
        owner_source_label: '电工填报',
        source_updated_at: '2026-06-11T09:20:00',
      },
    },
    streamStatus: 'open',
  })

  const energySource = surface.bottomStatus.find((item) => item.key === 'energy-source')
  const energyFill = surface.bottomStatus.find((item) => item.key === 'energy-fill')
  const energyPerTon = surface.bottomStatus.find((item) => item.key === 'energy-per-ton')

  assert.deepEqual(
    [energySource?.label, energySource?.value, energySource?.tone],
    ['能耗采集', '物联网采集 · 09:20', 'success'],
  )
  assert.deepEqual(
    [energyFill?.label, energyFill?.value, energyFill?.tone],
    ['电工填报', '8,700 kWh', 'success'],
  )
  assert.deepEqual(
    [energyPerTon?.label, energyPerTon?.value, energyPerTon?.tone],
    ['吨电耗', '无产量分母', 'warning'],
  )
})
