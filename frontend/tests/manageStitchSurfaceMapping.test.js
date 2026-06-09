import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  STITCH_MANAGE_SCREENS,
  buildEnergyStitchSurface,
  buildFillDetailsStitchSurface,
  buildLiveStitchSurface,
  buildProductionStitchSurface,
  buildTodayStitchSurface,
} from '../src/utils/stitchManageSurface.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('Stitch screen records pin the generated design evidence for ready manage pages', () => {
  assert.deepEqual(STITCH_MANAGE_SCREENS.today, {
    projectId: '3839293853809482256',
    screenId: 'd9646f7499664e2b988ff67670cc6214',
    route: '/manage/today',
  })
  assert.deepEqual(STITCH_MANAGE_SCREENS.live, {
    projectId: '3839293853809482256',
    screenId: '707c0acd1b3e4873a38973141ee5ff89',
    route: '/manage/live',
  })
  assert.deepEqual(STITCH_MANAGE_SCREENS.production, {
    projectId: '3839293853809482256',
    screenId: '3a7288d183ed48609f2f851097ded0cb',
    route: '/manage/production',
  })
  assert.deepEqual(STITCH_MANAGE_SCREENS.fillDetails, {
    projectId: '3839293853809482256',
    screenId: '23626a62189043148d752492349fbcab',
    route: '/manage/fill-details',
  })
  assert.deepEqual(STITCH_MANAGE_SCREENS.energy, {
    projectId: '3839293853809482256',
    screenId: '425e659eeb834f648f18039a38868034',
    route: '/manage/energy',
  })
})

test('today Stitch surface keeps the industrial slots wired to existing daily-report helpers', () => {
  const surface = buildTodayStitchSurface({
    snapshotData: {
      business_date: '2026-06-05',
      daily_overview: {
        plant_output: { daily_output: 343, monthly_output: 1494, energy_per_ton: 86.7 },
        contracts: { daily_new: 2422, unit: '吨' },
        energy: {
          total_electricity: 131500,
          owner_total_electricity: 130026,
          data_available: true,
        },
        yield_rates: { daily: 86.78, owner_daily: 83.69 },
        workshop_output: [
          { workshop: '轧制分厂', daily_output: 82, monthly_output: 348 },
          { workshop: '冷轧三车间', daily_output: 99, monthly_output: 99 },
        ],
        wip_distribution: [
          {
            workshop: '退火分厂',
            total_weight: 244,
            feeding_weight: 120.5,
            coil_count: 12,
          },
        ],
      },
    },
    liveAggregation: {
      workshops: [
        {
          workshop_id: 1,
          workshop_name: '铸锭车间',
          machines: [
            {
              machine_id: 11,
              machine_name: '1#炉',
              shifts: [
                {
                  shift_id: 101,
                  shift_name: '白班',
                  submission_status: 'not_started',
                  status_text: '缺报',
                },
              ],
            },
          ],
        },
      ],
    },
  })

  assert.equal(surface.stitch.screenId, 'd9646f7499664e2b988ff67670cc6214')
  assert.deepEqual(surface.slotOrder, [
    'statusBar',
    'kpiStrip',
    'productionFlow',
    'workshopTable',
    'wipDistribution',
    'eventRail',
    'bottomStatus',
  ])
  assert.equal(surface.businessDate, '2026-06-05')
  assert.equal(surface.kpiStrip.find((item) => item.key === 'plant-output')?.value, '343')
  assert.equal(surface.kpiStrip.find((item) => item.key === 'contract-tonnage')?.unit, '吨')
  assert.equal(surface.comparisonRail.find((item) => item.key === 'energy')?.primaryValue, '131,500 度')
  assert.deepEqual(surface.workshopTable.map((row) => row.workshop), ['轧制分厂'])
  assert.equal(surface.wipDistribution[0].feedingText, '投料 120.5 吨')
  assert.ok(surface.missingReportRows.length > 0)
  assert.equal(surface.bottomStatus.find((item) => item.key === 'system')?.value, '正常运行')
  assert.equal(surface.bottomStatus.find((item) => item.key === 'data')?.value, '生产日报已同步')
  assert.equal(surface.bottomStatus.find((item) => item.key === 'live')?.value, '实时聚合已同步')
})

test('today Stitch surface does not claim success when daily or realtime data is untrusted', () => {
  const failed = buildTodayStitchSurface({
    snapshotData: {},
    targetDate: '2026-06-05',
    liveAggregation: {},
    runtimeState: {
      snapshotError: '昨日总览数据加载失败',
      liveError: '实时聚合加载失败',
    },
  })
  const empty = buildTodayStitchSurface({
    snapshotData: {},
    targetDate: '2026-06-05',
    liveAggregation: {},
  })

  assert.equal(failed.bottomStatus.find((item) => item.key === 'system')?.value, '需核查')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'system')?.tone, 'danger')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'data')?.value, '日报未同步')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'data')?.tone, 'danger')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'live')?.value, '实时聚合待核')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'live')?.tone, 'danger')
  assert.equal(empty.bottomStatus.find((item) => item.key === 'system')?.value, '待核')
  assert.equal(empty.bottomStatus.find((item) => item.key === 'data')?.value, '暂无可信数据')
  assert.equal(empty.bottomStatus.find((item) => item.key === 'live')?.value, '实时聚合待核')
})

test('today Stitch surface keeps overall status pending when only one data source is trusted', () => {
  const dailyOnly = buildTodayStitchSurface({
    snapshotData: {
      daily_overview: {
        plant_output: { daily_output: 343 },
      },
    },
    liveAggregation: {},
  })
  const liveOnly = buildTodayStitchSurface({
    snapshotData: {},
    liveAggregation: { business_date: '2026-06-05' },
  })

  assert.equal(dailyOnly.bottomStatus.find((item) => item.key === 'system')?.value, '待核')
  assert.equal(dailyOnly.bottomStatus.find((item) => item.key === 'data')?.value, '生产日报已同步')
  assert.equal(dailyOnly.bottomStatus.find((item) => item.key === 'live')?.value, '实时聚合待核')
  assert.equal(liveOnly.bottomStatus.find((item) => item.key === 'system')?.value, '待核')
  assert.equal(liveOnly.bottomStatus.find((item) => item.key === 'data')?.value, '暂无可信数据')
  assert.equal(liveOnly.bottomStatus.find((item) => item.key === 'live')?.value, '实时聚合已同步')
})

test('live Stitch surface keeps realtime wall slots wired to aggregation and SSE state', () => {
  const surface = buildLiveStitchSurface({
    targetDate: '2026-06-05',
    streamStatus: 'closed',
    loadError: '',
    aggregation: {
      factory_total: {
        packaging_output: 126.42,
        finished_inbound_output: 120.5,
        process_output: 211.8,
      },
      energy_summary: {
        total_electricity: 17430,
        energy_per_ton: 64.2,
      },
      overall_progress: {
        missing_cell_count: 3,
        attention_cell_count: 5,
      },
      mes_sync_status: {
        lag_seconds: 84,
      },
      workshops: [
        {
          workshop_name: '在线退火分厂',
          machines: [
            {
              machine_id: 21,
              machine_name: '1#退火炉',
              day_total: { output: 30 },
              shifts: [{ shift_name: '白班', submission_status: 'all_submitted', is_applicable: true }],
            },
          ],
        },
      ],
    },
  })

  assert.equal(surface.stitch.screenId, '707c0acd1b3e4873a38973141ee5ff89')
  assert.deepEqual(surface.slotOrder, [
    'statusBar',
    'realtimeKpiStrip',
    'marketTicker',
    'machineMatrix',
    'mesDistribution',
    'eventRail',
    'drawer',
    'bottomStatus',
  ])
  assert.equal(surface.businessDate, '2026-06-05')
  assert.equal(surface.marketTicker.find((item) => item.label === '包装产量')?.value, '126.42 吨')
  assert.equal(surface.marketTicker.find((item) => item.label === '全厂入库产量')?.value, '120.5 吨')
  assert.equal(surface.marketTicker.find((item) => item.label === '总电耗')?.value, '17,430 kWh')
  assert.equal(surface.machineMatrix.machineCount, 1)
  assert.equal(surface.realtimeKpiStrip[0].primaryLabel, 'MES包装')
  assert.ok(surface.eventRail.find((item) => item.title === '实时连接断开'))
  assert.equal(surface.bottomStatus.find((item) => item.key === 'stream')?.value, '连接断开')
  assert.equal(surface.bottomStatus.find((item) => item.key === 'stream')?.tone, 'danger')
})

test('live Stitch surface translates internal realtime states into user-facing Chinese labels', () => {
  const reconnecting = buildLiveStitchSurface({
    streamStatus: 'reconnecting',
    aggregation: { business_date: '2026-06-05' },
  })
  const open = buildLiveStitchSurface({
    streamStatus: 'open',
    aggregation: { business_date: '2026-06-05' },
  })
  const idle = buildLiveStitchSurface({
    streamStatus: 'idle',
    aggregation: {},
  })

  assert.equal(reconnecting.bottomStatus.find((item) => item.key === 'stream')?.value, '实时重连')
  assert.equal(reconnecting.bottomStatus.find((item) => item.key === 'stream')?.tone, 'warning')
  assert.equal(open.bottomStatus.find((item) => item.key === 'stream')?.value, '实时正常')
  assert.equal(open.bottomStatus.find((item) => item.key === 'stream')?.tone, 'success')
  assert.equal(idle.bottomStatus.find((item) => item.key === 'stream')?.value, '等待连接')
  assert.equal(idle.bottomStatus.find((item) => item.key === 'stream')?.tone, 'warning')
})

test('production Stitch surface preserves existing KPI, ranking and source objects', () => {
  const kpiItems = [
    { key: 'output', label: '入库产量', value: '343', unit: '吨' },
    { key: 'energy', label: '日吨能耗', value: '64.2', unit: 'kWh/吨' },
  ]
  const rankedRows = [
    { key: 1, rank: 1, name: '精整车间', totalOutput: 128, progress: 88 },
    { key: 2, rank: 2, name: '拉矫车间', totalOutput: 96, progress: 72 },
  ]
  const sourceOverview = {
    business_date: '2026-06-05',
    total_contract_weight: 2422,
  }

  const surface = buildProductionStitchSurface({
    snapshotData: { business_date: '2026-06-05', production_lane: [{ workshop_name: '精整车间' }] },
    targetDate: '2026-06-05',
    kpiItems,
    rankedRows,
    sourceOverview,
  })

  assert.equal(surface.stitch.screenId, '3a7288d183ed48609f2f851097ded0cb')
  assert.deepEqual(surface.slotOrder, [
    'statusBar',
    'kpiStrip',
    'sourceOverview',
    'workshopRanking',
    'productionBrief',
    'signal',
    'bottomStatus',
  ])
  assert.equal(surface.businessDate, '2026-06-05')
  assert.deepEqual(surface.kpiStrip, kpiItems)
  assert.deepEqual(surface.workshopRanking, rankedRows)
  assert.deepEqual(surface.sourceOverview, sourceOverview)
  assert.equal(surface.bottomStatus.find((item) => item.key === 'system')?.value, '正常运行')
  assert.equal(surface.bottomStatus.find((item) => item.key === 'snapshot')?.value, '生产快照已同步')
})

test('production Stitch surface does not claim success while loading, failed or empty', () => {
  const loading = buildProductionStitchSurface({
    runtimeState: { snapshotLoading: true },
  })
  const failed = buildProductionStitchSurface({
    runtimeState: { snapshotError: '生产数据加载失败' },
  })
  const empty = buildProductionStitchSurface({})

  assert.equal(loading.bottomStatus.find((item) => item.key === 'system')?.value, '同步中')
  assert.equal(loading.bottomStatus.find((item) => item.key === 'system')?.tone, 'warning')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'system')?.value, '需核查')
  assert.equal(failed.bottomStatus.find((item) => item.key === 'snapshot')?.value, '生产快照未同步')
  assert.equal(empty.bottomStatus.find((item) => item.key === 'system')?.value, '待核')
  assert.equal(empty.bottomStatus.find((item) => item.key === 'snapshot')?.value, '暂无可信数据')
})

test('fill details Stitch surface preserves audit ticker, ledger rows and issue queues', () => {
  const kpiItems = [{ key: 'entry', label: '明细', value: 12, unit: '条' }]
  const auditTicker = [{ key: 'energy', label: '用电', value: '120 kWh', tone: 'success' }]
  const sourceChain = [{ key: 'yield', title: '成品率', primaryValue: '86%', compareValue: '85%' }]
  const issueQueues = [{ key: 'missing-energy', title: '缺能耗', count: 1, items: ['电工未填'] }]
  const ledgerRows = [{ rowId: 'r1', workshopName: '精整车间' }]
  const filteredRows = [{ rowId: 'r1', workshopName: '精整车间' }]

  const surface = buildFillDetailsStitchSurface({
    targetDate: '2026-06-05',
    kpiItems,
    auditTicker,
    sourceChain,
    issueQueues,
    ledgerRows,
    filteredRows,
    runtimeState: { loading: false, errorText: '' },
  })

  assert.equal(surface.stitch.screenId, '23626a62189043148d752492349fbcab')
  assert.deepEqual(surface.slotOrder, [
    'statusBar',
    'kpiStrip',
    'sourceChain',
    'ledgerTools',
    'ledgerTable',
    'issueQueues',
    'bottomStatus',
  ])
  assert.equal(surface.businessDate, '2026-06-05')
  assert.equal(surface.statusBar.filteredCount, 1)
  assert.deepEqual(surface.bottomStatus, [
    { key: 'system', label: '系统状态', value: '已同步', tone: 'success' },
    { key: 'ledger', label: '填报明细', value: '1 条', tone: 'success' },
    { key: 'filter', label: '当前筛选', value: '1 条', tone: 'success' },
  ])
  assert.deepEqual(surface.kpiStrip, kpiItems)
  assert.deepEqual(surface.auditTicker, auditTicker)
  assert.deepEqual(surface.sourceChain, sourceChain)
  assert.deepEqual(surface.issueQueues, issueQueues)
  assert.deepEqual(surface.ledgerRows, ledgerRows)
  assert.deepEqual(surface.filteredRows, filteredRows)
})

test('fill details Stitch surface exposes loading and error status without changing rows', () => {
  const loading = buildFillDetailsStitchSurface({
    filteredRows: [],
    runtimeState: { loading: true },
  })
  const failed = buildFillDetailsStitchSurface({
    filteredRows: [],
    runtimeState: { errorText: '加载填报明细失败' },
  })

  assert.equal(loading.statusBar.syncStatus, '同步中')
  assert.equal(loading.statusBar.tone, 'warning')
  assert.equal(loading.bottomStatus[0].value, '同步中')
  assert.equal(loading.bottomStatus[0].tone, 'warning')
  assert.equal(failed.statusBar.syncStatus, '需核查')
  assert.equal(failed.statusBar.tone, 'danger')
  assert.equal(failed.bottomStatus[0].value, '需核查')
  assert.equal(failed.bottomStatus[0].tone, 'danger')
})

test('energy Stitch surface preserves energy KPIs, detail rows and source status', () => {
  const kpiItems = [
    { key: 'electricity', label: '电耗', value: '131,500', unit: 'kWh', accent: 'cyan' },
    { key: 'gas', label: '气耗', value: '53,433', unit: 'm³', accent: 'amber' },
    { key: 'water', label: '水耗', value: '20', unit: 'm³', accent: 'blue' },
    { key: 'total', label: '总能耗', value: '53,433', unit: 'kgce', accent: 'cyan' },
    { key: 'output', label: '产量', value: '45', unit: '吨', accent: 'blue' },
    { key: 'per-ton-peak', label: '单吨峰值', value: '20', unit: 'kgce/吨', accent: 'amber' },
  ]
  const detailRows = [
    {
      business_date: '2026-06-05',
      workshop_code: '精整车间',
      shift_code: 'day',
      electricity_value: 1200,
      gas_value: 320,
      water_value: 18,
      total_energy: 660,
      output_weight: 34,
      energy_per_ton: 19.41,
    },
    {
      business_date: '2026-06-05',
      workshop_code: '拉矫车间',
      shift_code: 'night',
      electricity_value: 300,
      gas_value: 120,
      water_value: 8,
      total_energy: 220,
      output_weight: 11,
      energy_per_ton: 20,
    },
  ]

  const surface = buildEnergyStitchSurface({
    targetDate: '2026-06-05',
    kpiItems,
    detailRows,
    runtimeState: { loading: false, errorText: '', updatedAt: '08:30:00' },
  })

  assert.equal(surface.stitch.screenId, '425e659eeb834f648f18039a38868034')
  assert.deepEqual(surface.slotOrder, [
    'statusBar',
    'kpiStrip',
    'energyFlow',
    'detailTable',
    'eventRail',
    'bottomStatus',
  ])
  assert.equal(surface.businessDate, '2026-06-05')
  assert.deepEqual(surface.kpiStrip, kpiItems)
  assert.notDeepEqual(surface.energyFlow, kpiItems)
  assert.deepEqual(surface.energyFlow.map((item) => item.key), [
    'electricity-input',
    'gas-input',
    'water-input',
    'total-output',
    'per-ton-check',
  ])
  assert.deepEqual(surface.energyFlow.map((item) => item.stage), ['采集', '采集', '采集', '折算', '校核'])
  assert.deepEqual(surface.energyFlow.map((item) => item.icon), ['meter', 'flame', 'water', 'converter', 'gauge'])
  assert.equal(surface.energyFlow.find((item) => item.key === 'electricity-input')?.source, '能耗汇总接口')
  assert.equal(surface.energyFlow.find((item) => item.key === 'total-output')?.label, '综合折算')
  assert.equal(surface.energyFlow.find((item) => item.key === 'total-output')?.tone, 'result')
  assert.equal(surface.energyFlow.find((item) => item.key === 'total-output')?.emphasis, 'endpoint')
  assert.equal(surface.energyFlow.find((item) => item.key === 'per-ton-check')?.value, '拉矫车间 20')
  assert.equal(surface.energyFlow.find((item) => item.key === 'per-ton-check')?.unit, 'kgce/吨')
  assert.equal(surface.energyFlow.find((item) => item.key === 'per-ton-check')?.tone, 'critical')
  assert.equal(surface.energyFlow.find((item) => item.key === 'per-ton-check')?.emphasis, 'endpoint')
  assert.deepEqual(surface.detailRows, detailRows)
  assert.equal(surface.statusBar.syncStatus, '已同步')
  assert.equal(surface.statusBar.updatedAt, '08:30:00')
  assert.equal(surface.eventRail[0].title, '能耗数据已同步')
  assert.ok(surface.eventRail.length >= 5)
  assert.equal(surface.eventRail.find((item) => item.key === 'electricity-top')?.value, '精整车间 1,200 kWh')
  assert.equal(surface.eventRail.find((item) => item.key === 'gas-top')?.value, '精整车间 320 m³')
  assert.equal(surface.eventRail.find((item) => item.key === 'water-top')?.value, '精整车间 18 m³')
  assert.equal(surface.eventRail.find((item) => item.key === 'output-top')?.value, '精整车间 34 吨')
  assert.equal(surface.eventRail.find((item) => item.key === 'per-ton-top')?.value, '拉矫车间 20 kgce/吨')
  assert.deepEqual(surface.bottomStatus, [
    { key: 'system', label: '系统状态', value: '已同步', tone: 'success' },
    { key: 'energy', label: '能耗明细', value: '2 条', tone: 'success' },
    { key: 'source', label: '数据来源', value: '能耗汇总接口', tone: 'success' },
    { key: 'updated-at', label: '页面刷新', value: '08:30:00', tone: 'success' },
  ])
})

test('energy Stitch surface exposes loading, empty and error states without changing rows', () => {
  const loading = buildEnergyStitchSurface({
    runtimeState: { loading: true },
  })
  const empty = buildEnergyStitchSurface({})
  const failed = buildEnergyStitchSurface({
    detailRows: [],
    runtimeState: { errorText: '能耗数据加载失败' },
  })

  assert.equal(loading.statusBar.syncStatus, '同步中')
  assert.equal(loading.statusBar.updatedAt, '-')
  assert.equal(loading.bottomStatus[0].tone, 'warning')
  assert.equal(loading.bottomStatus.find((item) => item.key === 'updated-at')?.value, '-')
  assert.equal(empty.statusBar.syncStatus, '待核')
  assert.equal(empty.bottomStatus[1].value, '0 条')
  assert.equal(empty.eventRail[0].title, '暂无能耗明细')
  assert.equal(failed.statusBar.syncStatus, '需核查')
  assert.equal(failed.bottomStatus[0].tone, 'danger')
  assert.equal(failed.eventRail[0].title, '能耗数据需核查')
  assert.equal(failed.eventRail[0].value, '能耗数据加载失败')
})

test('today, live, production, fill details and energy pages consume the Stitch surface mapping layer before visual rendering', () => {
  const todaySource = source('../src/views/manage/today/TodayPage.vue')
  const liveSource = source('../src/views/manage/live/LiveDashboardPage.vue')
  const productionSource = source('../src/views/manage/production/ProductionPage.vue')
  const fillDetailsSource = source('../src/views/manage/fill-details/FillDetailsPage.vue')
  const energySource = source('../src/views/energy/EnergyCenter.vue')

  assert.match(todaySource, /buildTodayStitchSurface/)
  assert.match(liveSource, /buildLiveStitchSurface/)
  assert.match(productionSource, /buildProductionStitchSurface/)
  assert.match(fillDetailsSource, /buildFillDetailsStitchSurface/)
  assert.match(energySource, /buildEnergyStitchSurface/)

  for (const pageSource of [todaySource, liveSource, productionSource, fillDetailsSource, energySource]) {
    assert.match(pageSource, /:data-stitch-project-id="stitchSurface\.stitch\.projectId"/)
    assert.match(pageSource, /:data-stitch-screen-id="stitchSurface\.stitch\.screenId"/)
  }
})

test('first-batch pages render the Stitch bottom status slot from real surface data', () => {
  const todaySource = source('../src/views/manage/today/TodayPage.vue')
  const liveSource = source('../src/views/manage/live/LiveDashboardPage.vue')

  assert.match(todaySource, /data-testid="stitch-bottom-status"/)
  assert.match(todaySource, /runtimeState/)
  assert.match(todaySource, /missingRows\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.missingReportRows/)
  assert.match(todaySource, /bottomStatusItems\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.bottomStatus/)
  assert.match(liveSource, /data-testid="stitch-bottom-status"/)
  assert.match(liveSource, /bottomStatusItems\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.bottomStatus/)
})
