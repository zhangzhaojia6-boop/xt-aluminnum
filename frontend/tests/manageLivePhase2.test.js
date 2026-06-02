import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

import {
  buildLiveEventItems,
  buildLiveMachineMatrix,
  buildLiveMetricCompareItems,
  buildLiveTickerItems,
  formatTrustedMetric,
  shouldReloadForRealtimeEvent,
} from '../src/utils/liveDashboardPhase2.js'

const livePageUrl = new URL('../src/views/manage/live/LiveDashboardPage.vue', import.meta.url)
const livePageSource = existsSync(livePageUrl) ? readFileSync(livePageUrl, 'utf8') : ''

const componentNames = [
  'LiveMarketTicker',
  'LiveMachineMatrix',
  'LiveMachineCard',
  'LiveEventRail',
  'LiveMetricCompareCard',
  'LiveMachineDrawer',
  'LiveDataStatePanel',
]

test('/manage/live uses the phase 2 Stitch component surface', () => {
  assert.ok(livePageSource, 'LiveDashboardPage.vue should exist')
  assert.doesNotMatch(livePageSource, /views\/reports\/LiveDashboard|reports\/LiveDashboard/)

  for (const name of componentNames) {
    assert.ok(
      existsSync(new URL(`../src/views/manage/live/${name}.vue`, import.meta.url)),
      `${name}.vue should exist`,
    )
  }

  assert.match(livePageSource, /fetchLiveAggregation/)
  assert.match(livePageSource, /fetchLiveCellDetail/)
  assert.match(livePageSource, /fetchLiveFillDetails/)
  assert.match(livePageSource, /useRealtimeStream/)
  assert.match(livePageSource, /connectionTimeoutMs:\s*15000/)
  assert.match(livePageSource, /快照可用 · 实时重连/)
  assert.match(livePageSource, /if \(loading\.value\) return '快照加载中'/)
})

test('realtime stream heartbeats do not reload the whole live page', () => {
  assert.equal(
    shouldReloadForRealtimeEvent({ type: 'heartbeat', payload: {}, targetDate: '2026-05-30' }),
    false,
  )
  assert.equal(
    shouldReloadForRealtimeEvent({
      type: 'entry_submitted',
      payload: { business_date: '2026-05-29' },
      targetDate: '2026-05-30',
    }),
    false,
  )
  assert.equal(
    shouldReloadForRealtimeEvent({
      type: 'entry_submitted',
      payload: { business_date: '2026-05-30' },
      targetDate: '2026-05-30',
    }),
    true,
  )
})

test('ticker exposes the first-screen factory signals without fake zeros', () => {
  const items = buildLiveTickerItems({
    factory_total: {
      storage_finished_weight: 126.42,
      output: 211.8,
    },
    energy_summary: {},
    overall_progress: {
      missing_cell_count: 3,
      attention_cell_count: 5,
    },
    mes_sync_status: {
      lag_seconds: 84,
    },
  })

  assert.deepEqual(items.map((item) => item.label), [
    '成品入库',
    '过站下机',
    '总电耗',
    '吨电耗',
    '未填',
    '异常',
    '外部 MES',
  ])
  assert.equal(items[0].value, '126.42 吨')
  assert.equal(items[1].value, '211.8 吨')
  assert.equal(items[2].value, '暂无可信数据')
  assert.equal(items[3].value, '暂无可信数据')
  assert.equal(items[2].value.includes('0 kWh'), false)
})

test('ticker marks missing freshness and counts as unknown rather than healthy', () => {
  const items = buildLiveTickerItems({})

  assert.equal(items.find((item) => item.label === '未填')?.tone, 'muted')
  assert.equal(items.find((item) => item.label === '异常')?.tone, 'muted')
  assert.equal(items.find((item) => item.label === '外部 MES')?.tone, 'muted')
})

test('machine matrix hides removed workshops and separates pending ownership', () => {
  const matrix = buildLiveMachineMatrix([
    {
      workshop_name: '在线退火分厂',
      machines: [
        {
          machine_id: 21,
          machine_name: '1#退火炉',
          day_total: { output: 30 },
          shifts: [{ shift_name: '大夜', submission_status: 'all_submitted', is_applicable: true }],
        },
        {
          machine_id: -5,
          machine_name: '未绑定机列 / 大夜',
          machine_binding_status: 'unbound',
          day_total: { output: 12 },
          shifts: [{ shift_name: '大夜', submission_status: 'in_progress', is_applicable: true }],
        },
      ],
    },
    {
      workshop_name: '冷轧三车间',
      is_removed: true,
      machines: [
        {
          machine_id: 31,
          machine_name: '旧机列',
          day_total: { output: 99 },
          shifts: [{ shift_name: '大夜', submission_status: 'all_submitted', is_applicable: true }],
        },
      ],
    },
  ])

  assert.equal(matrix.workshops.length, 1)
  assert.equal(matrix.workshops[0].workshopName, '在线退火分厂')
  assert.equal(matrix.workshops[0].machines.length, 1)
  assert.equal(matrix.pendingMachines.length, 1)
  assert.equal(matrix.pendingMachines[0].machineName, '未绑定机列 / 大夜')
})

test('metric comparison keeps algorithm values primary and filled values visible', () => {
  const items = buildLiveMetricCompareItems({
    factory_total: {
      storage_finished_weight: 126.4,
      owner_storage_finished_weight: 120.8,
    },
    energy_summary: {
      algorithm_total_energy: 8840,
      owner_total_electricity: 8700,
      algorithm_energy_per_ton: 69.94,
    },
  })

  assert.equal(items[0].label, '全厂总产量')
  assert.equal(items[0].primaryLabel, '算法')
  assert.equal(items[0].primaryValue, '126.4 吨')
  assert.equal(items[0].compareLabel, '填报')
  assert.equal(items[0].compareValue, '120.8 吨')
  assert.equal(items[1].primaryValue, '8,840 kWh')
  assert.equal(items[1].compareValue, '8,700 kWh')
})

test('event rail and trusted metric formatting expose empty, error and disconnected states', () => {
  assert.equal(formatTrustedMetric(null, 'kWh'), '暂无可信数据')
  assert.equal(formatTrustedMetric(undefined, '吨'), '暂无可信数据')
  assert.equal(formatTrustedMetric(0, 'kWh'), '0 kWh')

  const events = buildLiveEventItems({
    streamStatus: 'reconnecting',
    loadError: '接口失败',
    aggregation: {
      overall_progress: { missing_cell_count: 2 },
      energy_summary: {},
      data_quality: {
        missing_output_weight: { entry_count: 4 },
      },
    },
  })

  assert.equal(events.some((event) => event.title === '实时连接断开'), true)
  assert.equal(events.some((event) => event.title === '接口失败'), true)
  assert.equal(events.some((event) => event.title === '未填报'), true)
  assert.equal(events.some((event) => event.title === '无能耗可信数据'), true)
  assert.equal(events.some((event) => event.title === '待补产出重量'), true)
})
