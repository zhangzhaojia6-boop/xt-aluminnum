import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

import {
  buildLiveEventItems,
  buildLiveMachineMatrix,
  buildLiveMetricCompareItems,
  buildLivePriorityItems,
  buildLiveTickerItems,
  formatTrustedMetric,
  shouldReloadForRealtimeEvent,
  mergeRealtimeEventPatch,
} from '../src/utils/liveDashboardPhase2.js'

const livePageUrl = new URL('../src/views/manage/live/LiveDashboardPage.vue', import.meta.url)
const livePageSource = existsSync(livePageUrl) ? readFileSync(livePageUrl, 'utf8') : ''
const animatedMetricUrl = new URL('../src/views/manage/live/AnimatedMetricValue.vue', import.meta.url)
const animatedMetricSource = existsSync(animatedMetricUrl) ? readFileSync(animatedMetricUrl, 'utf8') : ''
const marketTickerUrl = new URL('../src/views/manage/live/LiveMarketTicker.vue', import.meta.url)
const marketTickerSource = existsSync(marketTickerUrl) ? readFileSync(marketTickerUrl, 'utf8') : ''

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
  assert.match(livePageSource, /connectionTimeoutMs:\s*10000/)
  assert.match(livePageSource, /快照可用 · 实时重连/)
  assert.match(livePageSource, /接口核验中 · 快照兜底/)
  assert.match(livePageSource, /if \(loading\.value\) return '快照加载中'/)
})

test('/manage/live event rail mirrors the snapshot fallback connection wording', () => {
  const eventRailSource = readFileSync(
    new URL('../src/views/manage/live/LiveEventRail.vue', import.meta.url),
    'utf8',
  )

  assert.match(eventRailSource, /接口核验中 · 快照兜底/)
  assert.doesNotMatch(eventRailSource, /正在连接/)
})

test('/manage/live publishes the primary snapshot before secondary fill details settle', () => {
  const liveAwaitIndex = livePageSource.indexOf('const liveData = await fetchLiveAggregation')
  const publishIndex = livePageSource.indexOf('aggregation.value = liveData')
  const detailRefreshIndex = livePageSource.indexOf('void refreshFillDetails')

  assert.notEqual(liveAwaitIndex, -1)
  assert.notEqual(publishIndex, -1)
  assert.notEqual(detailRefreshIndex, -1)
  assert.ok(liveAwaitIndex < publishIndex)
  assert.ok(publishIndex < detailRefreshIndex)
  assert.match(livePageSource, /includeDetails:\s*false/)
  assert.match(livePageSource, /void loadDashboardSurface\(\)/)
})

test('/manage/live keeps the dispatch wall title readable at dashboard width', () => {
  assert.match(livePageSource, /font-size:\s*clamp\(28px,\s*3vw,\s*44px\)/)
  assert.match(livePageSource, /white-space:\s*nowrap/)
})

test('/manage/live uses one-second numeric rolling without heavy decorative loops', () => {
  assert.ok(animatedMetricSource, 'AnimatedMetricValue.vue should exist')
  assert.match(animatedMetricSource, /const durationMs = 1000/)
  assert.match(animatedMetricSource, /prefers-reduced-motion:\s*reduce/)
  assert.doesNotMatch(animatedMetricSource, /@keyframes/)
  assert.doesNotMatch(animatedMetricSource, /infinite/)
})

test('/manage/live top ticker uses large readable cards without heavy loops', () => {
  assert.ok(marketTickerSource, 'LiveMarketTicker.vue should exist')
  assert.match(marketTickerSource, /aria-live="polite"/)
  assert.match(marketTickerSource, /来源 \{\{ item\.source \}\}/)
  assert.match(marketTickerSource, /font-size:\s*clamp\(32px,\s*3\.2vw,\s*52px\)/)
  assert.doesNotMatch(marketTickerSource, /@keyframes/)
  assert.doesNotMatch(marketTickerSource, /infinite/)
})

test('realtime stream heartbeats do not reload the whole live page', () => {
  assert.equal(
    shouldReloadForRealtimeEvent({ type: 'heartbeat', payload: {}, targetDate: '2026-05-30' }),
    false,
  )
  assert.equal(
    shouldReloadForRealtimeEvent({ type: 'message', payload: {}, targetDate: '2026-05-30' }),
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

test('/manage/live coalesces realtime snapshot reloads to avoid request storms', () => {
  assert.match(livePageSource, /let\s+dashboardLoadPromise\s*=\s*null/)
  assert.match(livePageSource, /if\s*\(dashboardLoadPromise\)\s*return\s+dashboardLoadPromise/)
  assert.match(livePageSource, /function\s+scheduleRealtimeSnapshotReload/)
  assert.match(livePageSource, /REALTIME_RELOAD_DEBOUNCE_MS\s*=\s*5000/)
  assert.doesNotMatch(livePageSource, /void\s+loadDashboardSurface\(\{\s*silent:\s*streamOpen,\s*includeDetails:\s*!streamOpen\s*\}\)/)
})

test('ticker exposes the first-screen factory signals with zero fallback', () => {
  const items = buildLiveTickerItems({
    factory_total: {
      packaging_output: 126.42,
      finished_inbound_output: 120.5,
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
    'MES包装产量',
    '内勤入库填报',
    '过站下机',
    '总电耗',
    '吨电耗',
    '未填',
    '异常',
    '外部 MES',
  ])
  assert.equal(items[0].value, '126.42 吨')
  assert.equal(items[1].value, '120.5 吨')
  assert.equal(items[0].source, 'MES包装')
  assert.equal(items[1].source, '内勤入库')
  assert.equal(items[2].value, '211.8 吨')
  assert.equal(items[3].value, '0 kWh')
  assert.equal(items[4].value, '0 kWh/吨')
})

test('ticker accepts daily energy aliases from the energy center summary', () => {
  const items = buildLiveTickerItems({
    energy_summary: {
      total_electricity: 17430,
      energy_per_ton: 64.2,
    },
  })

  assert.equal(items.find((item) => item.label === '总电耗')?.value, '17,430 kWh')
  assert.equal(items.find((item) => item.label === '吨电耗')?.value, '64.2 kWh/吨')
})

test('ticker does not display comprehensive total_energy as electricity', () => {
  const items = buildLiveTickerItems({
    energy_summary: {
      total_energy: 17430,
    },
  })

  assert.equal(items.find((item) => item.label === '总电耗')?.value, '0 kWh')
})

test('ticker honors unavailable energy flag with zero value and muted tone', () => {
  const items = buildLiveTickerItems({
    energy_summary: {
      data_available: false,
      total_electricity: 0,
      energy_per_ton: 0,
    },
  })

  assert.equal(items.find((item) => item.label === '总电耗')?.value, '0 kWh')
  assert.equal(items.find((item) => item.label === '吨电耗')?.value, '0 kWh/吨')
  assert.equal(items.find((item) => item.label === '总电耗')?.tone, 'muted')
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

test('machine matrix orders shifts by production day rhythm', () => {
  const matrix = buildLiveMachineMatrix([
    {
      workshop_name: '冷轧',
      machines: [
        {
          machine_id: 21,
          machine_name: '1#机',
          shifts: [
            { shift_name: '大夜', submission_status: 'all_submitted', is_applicable: true },
            { shift_name: '小夜', submission_status: 'all_submitted', is_applicable: true },
            { shift_name: '白班', submission_status: 'all_submitted', is_applicable: true },
          ],
        },
      ],
    },
  ])

  assert.deepEqual(
    matrix.workshops[0].machines[0].shifts.map((shift) => shift.shiftName),
    ['长白班', '小夜班', '大夜班'],
  )
})

test('metric comparison keeps algorithm values primary and filled values visible', () => {
  const items = buildLiveMetricCompareItems({
    factory_total: {
      packaging_output: 126.4,
      finished_inbound_output: 120.8,
    },
    energy_summary: {
      algorithm_total_energy: 8840,
      owner_total_electricity: 8700,
      algorithm_energy_per_ton: 69.94,
    },
  })

  assert.equal(items[0].label, '全厂总产量')
  assert.equal(items[0].primaryLabel, 'MES包装')
  assert.equal(items[0].primaryValue, '126.4 吨')
  assert.equal(items[0].compareLabel, '全厂入库')
  assert.equal(items[0].compareValue, '120.8 吨')
  assert.equal(items[1].primaryValue, '8,840 kWh')
  assert.equal(items[1].compareValue, '8,700 kWh')
})

test('metric comparison accepts electrician fill aliases without saying missing', () => {
  const items = buildLiveMetricCompareItems({
    energy_summary: {
      total_electricity: 17430,
      owner_total_electricity: 17020,
      energy_per_ton: 64.2,
    },
  })

  assert.equal(items[1].primaryValue, '17,430 kWh')
  assert.equal(items[1].compareValue, '17,020 kWh')
  assert.equal(items[2].primaryValue, '64.2 kWh/吨')
})

test('metric comparison does not display total_energy as total electricity', () => {
  const items = buildLiveMetricCompareItems({
    energy_summary: {
      total_energy: 17430,
      owner_total_electricity: 17020,
    },
  })

  assert.equal(items[1].primaryValue, '0 kWh')
  assert.equal(items[1].compareValue, '17,020 kWh')
})

test('metric comparison honors unavailable energy flag instead of showing fake zero', () => {
  const items = buildLiveMetricCompareItems({
    energy_summary: {
      data_available: false,
      total_electricity: 0,
      energy_per_ton: 0,
      owner_total_electricity: 0,
    },
  })

  assert.equal(items[1].primaryValue, '0 kWh')
  assert.equal(items[1].compareValue, '0 kWh')
  assert.equal(items[2].primaryValue, '0 kWh/吨')
})

test('event rail and trusted metric formatting expose empty, error and disconnected states', () => {
  assert.equal(formatTrustedMetric(null, 'kWh'), '0 kWh')
  assert.equal(formatTrustedMetric(undefined, '吨'), '0 吨')
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
  assert.equal(events.some((event) => event.title === '能耗待同步'), true)
  assert.equal(events.some((event) => event.title === '待补产出重量'), true)
})

test('realtime event payload can patch live aggregation without visible full-page reload', () => {
  const patched = mergeRealtimeEventPatch(
    { factory_total: { packaging_output: 10 }, energy_summary: { total_electricity: 80 } },
    {
      targetDate: '2026-06-09',
      payload: {
        business_date: '2026-06-09',
        factory_total: { packaging_output: 12.5 },
        energy_summary: { total_electricity: 96 },
      },
    },
  )

  assert.equal(patched.factory_total.packaging_output, 12.5)
  assert.equal(patched.energy_summary.total_electricity, 96)
})

test('live priority items expose only the three most urgent actions', () => {
  const items = buildLivePriorityItems([
    { title: '实时连接断开', tone: 'warning', text: '正在重连' },
    { title: '接口失败', tone: 'danger', text: '接口失败' },
    { title: '未填报', tone: 'danger', text: '141 个班次' },
    { title: '能耗待同步', tone: 'warning', text: '等待电工或算法能耗明细' },
  ])

  assert.equal(items.length, 3)
  assert.deepEqual(items.map((item) => item.rank), [1, 2, 3])
  assert.deepEqual(items.map((item) => item.title), ['接口失败', '未填报', '实时连接断开'])
})
