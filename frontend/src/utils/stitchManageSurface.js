import {
  buildDailyComparisonCards,
  buildDailySettlementCards,
  buildDailyWorkshopRows,
  buildDailyWipRows,
} from './manageDailyReportSurface.js'
import { buildMissingReportRows } from './missingReportRows.js'
import {
  buildLiveEventItems,
  buildLiveMachineMatrix,
  buildLiveMetricCompareItems,
  buildLivePriorityItems,
  buildLiveProcessFlowItems,
  buildLiveTickerItems,
} from './liveDashboardPhase2.js'

export const STITCH_MANAGE_SCREENS = {
  today: {
    projectId: '3839293853809482256',
    screenId: 'd9646f7499664e2b988ff67670cc6214',
    route: '/manage/today',
  },
  live: {
    projectId: '3839293853809482256',
    screenId: '707c0acd1b3e4873a38973141ee5ff89',
    route: '/manage/live',
  },
  production: {
    projectId: '3839293853809482256',
    screenId: '3a7288d183ed48609f2f851097ded0cb',
    route: '/manage/production',
  },
  fillDetails: {
    projectId: '3839293853809482256',
    screenId: '23626a62189043148d752492349fbcab',
    route: '/manage/fill-details',
  },
  energy: {
    projectId: '3839293853809482256',
    screenId: '425e659eeb834f648f18039a38868034',
    route: '/manage/energy',
  },
}

export const TODAY_STITCH_SLOT_ORDER = [
  'statusBar',
  'kpiStrip',
  'productionFlow',
  'workshopTable',
  'wipDistribution',
  'eventRail',
  'bottomStatus',
]

export const LIVE_STITCH_SLOT_ORDER = [
  'statusBar',
  'realtimeKpiStrip',
  'marketTicker',
  'processFlow',
  'machineMatrix',
  'mesDistribution',
  'eventRail',
  'drawer',
  'bottomStatus',
]

export const PRODUCTION_STITCH_SLOT_ORDER = [
  'statusBar',
  'kpiStrip',
  'sourceOverview',
  'workshopRanking',
  'productionBrief',
  'signal',
  'bottomStatus',
]

export const FILL_DETAILS_STITCH_SLOT_ORDER = [
  'statusBar',
  'kpiStrip',
  'sourceChain',
  'ledgerTools',
  'ledgerTable',
  'issueQueues',
  'bottomStatus',
]

export const ENERGY_STITCH_SLOT_ORDER = [
  'statusBar',
  'kpiStrip',
  'energyFlow',
  'detailTable',
  'eventRail',
  'bottomStatus',
]

function resolveBusinessDate(primary, ...fallbacks) {
  return [primary, ...fallbacks].find((value) => value) || ''
}

function hasRecordValue(record) {
  return Boolean(record && typeof record === 'object' && Object.keys(record).length)
}

function hasDailyOverview(overview) {
  return hasRecordValue(overview)
}

function hasLiveAggregation(aggregation) {
  if (!hasRecordValue(aggregation)) return false
  if (aggregation.business_date || aggregation.businessDate) return true
  if (Array.isArray(aggregation.workshops) && aggregation.workshops.length) return true
  return Boolean(aggregation.overall_progress || aggregation.factory_total)
}

function buildTodayBottomStatus({
  overview = {},
  liveAggregation = {},
  runtimeState = {},
} = {}) {
  const {
    snapshotLoading = false,
    snapshotError = '',
    liveLoading = false,
    liveError = '',
  } = runtimeState
  const dailyReady = hasDailyOverview(overview)
  const liveReady = hasLiveAggregation(liveAggregation)
  const anyLoading = snapshotLoading || liveLoading
  const anyError = Boolean(snapshotError || liveError)
  const allReady = dailyReady && liveReady

  return [
    {
      key: 'system',
      label: '系统状态',
      value: anyLoading ? '同步中' : (anyError ? '需核查' : (allReady ? '正常运行' : '待核')),
      tone: anyLoading ? 'warning' : (anyError ? 'danger' : (allReady ? 'success' : 'warning')),
    },
    {
      key: 'data',
      label: '数据源状态',
      value: snapshotLoading ? '日报同步中' : (snapshotError ? '日报未同步' : (dailyReady ? '生产日报已同步' : '暂无可信数据')),
      tone: snapshotLoading ? 'warning' : (snapshotError ? 'danger' : (dailyReady ? 'success' : 'warning')),
    },
    {
      key: 'live',
      label: '实时聚合',
      value: liveLoading ? '同步中' : (liveError || !liveReady ? '实时聚合待核' : '实时聚合已同步'),
      tone: liveLoading ? 'warning' : (liveError ? 'danger' : (liveReady ? 'success' : 'warning')),
    },
  ]
}

function resolveStreamStatus(status) {
  if (status === 'open') {
    return { value: '实时正常', tone: 'success' }
  }
  if (status === 'closed' || status === 'error') {
    return { value: '连接断开', tone: 'danger' }
  }
  if (status === 'reconnecting') {
    return { value: '实时重连', tone: 'warning' }
  }
  return { value: '等待连接', tone: 'warning' }
}

function buildProductionBottomStatus({
  snapshotData = {},
  sourceOverview = {},
  runtimeState = {},
} = {}) {
  const { snapshotLoading = false, snapshotError = '' } = runtimeState
  const snapshotReady = hasRecordValue(snapshotData)
  const sourceReady = hasRecordValue(sourceOverview)

  return [
    {
      key: 'system',
      label: '系统状态',
      value: snapshotLoading ? '同步中' : (snapshotError ? '需核查' : (snapshotReady ? '正常运行' : '待核')),
      tone: snapshotLoading ? 'warning' : (snapshotError ? 'danger' : (snapshotReady ? 'success' : 'warning')),
    },
    {
      key: 'snapshot',
      label: '生产快照',
      value: snapshotLoading ? '生产快照同步中' : (snapshotError ? '生产快照未同步' : (snapshotReady ? '生产快照已同步' : '暂无可信数据')),
      tone: snapshotLoading ? 'warning' : (snapshotError ? 'danger' : (snapshotReady ? 'success' : 'warning')),
    },
    {
      key: 'source',
      label: '主数据摘要',
      value: sourceReady ? '主数据已同步' : '主数据待核',
      tone: sourceReady ? 'success' : 'warning',
    },
  ]
}

function buildFillDetailsStatusBar({
  targetDate = '',
  filteredRows = [],
  runtimeState = {},
} = {}) {
  const { loading = false, errorText = '' } = runtimeState
  return {
    title: '填报明细',
    subtitle: '数据链路',
    businessDate: targetDate,
    filteredCount: filteredRows.length,
    syncStatus: loading ? '同步中' : (errorText ? '需核查' : '已同步'),
    tone: loading ? 'warning' : (errorText ? 'danger' : 'success'),
  }
}

function buildFillDetailsBottomStatus({
  ledgerRows = [],
  filteredRows = [],
  runtimeState = {},
} = {}) {
  const { loading = false, errorText = '' } = runtimeState
  const syncValue = loading ? '同步中' : (errorText ? '需核查' : '已同步')
  const syncTone = loading ? 'warning' : (errorText ? 'danger' : 'success')
  const ledgerCount = Array.isArray(ledgerRows) ? ledgerRows.length : 0
  const filteredCount = Array.isArray(filteredRows) ? filteredRows.length : 0

  return [
    { key: 'system', label: '系统状态', value: syncValue, tone: syncTone },
    { key: 'ledger', label: '填报明细', value: `${ledgerCount} 条`, tone: ledgerCount > 0 ? 'success' : 'warning' },
    { key: 'filter', label: '当前筛选', value: `${filteredCount} 条`, tone: filteredCount > 0 ? 'success' : 'warning' },
  ]
}

function resolveEnergySyncState({
  detailRows = [],
  runtimeState = {},
} = {}) {
  const { loading = false, errorText = '' } = runtimeState
  if (loading) {
    return { value: '同步中', tone: 'warning', eventTitle: '能耗数据同步中' }
  }
  if (errorText) {
    return { value: '需核查', tone: 'danger', eventTitle: '能耗数据需核查' }
  }
  if (Array.isArray(detailRows) && detailRows.length > 0) {
    return { value: '已同步', tone: 'success', eventTitle: '能耗数据已同步' }
  }
  return { value: '待核', tone: 'warning', eventTitle: '暂无能耗明细' }
}

function resolveEnergyUpdatedAt(runtimeState = {}) {
  return runtimeState.updatedAt || '-'
}

function toFiniteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatEnergyNumber(value) {
  const number = toFiniteNumber(value)
  if (number === null) return '-'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(number)
}

function findMaxEnergyRow(detailRows = [], key) {
  return detailRows.reduce((winner, row) => {
    const value = toFiniteNumber(row?.[key])
    if (value === null) return winner
    if (!winner || value > winner.value) {
      return { row, value }
    }
    return winner
  }, null)
}

function findKpiItem(kpiItems = [], key) {
  return kpiItems.find((item) => item?.key === key) || {}
}

function buildEnergyFlow({
  kpiItems = [],
  detailRows = [],
} = {}) {
  const electricity = findKpiItem(kpiItems, 'electricity')
  const gas = findKpiItem(kpiItems, 'gas')
  const water = findKpiItem(kpiItems, 'water')
  const total = findKpiItem(kpiItems, 'total')
  const maxPerTon = findMaxEnergyRow(detailRows, 'energy_per_ton')

  return [
    {
      key: 'electricity-input',
      stage: '采集',
      label: '电耗采集',
      value: electricity.value || '-',
      unit: electricity.unit || 'kWh',
      source: '能耗汇总接口',
      tone: 'cyan',
      icon: 'meter',
    },
    {
      key: 'gas-input',
      stage: '采集',
      label: '气耗采集',
      value: gas.value || '-',
      unit: gas.unit || 'm³',
      source: '能耗汇总接口',
      tone: 'amber',
      icon: 'flame',
    },
    {
      key: 'water-input',
      stage: '采集',
      label: '水耗采集',
      value: water.value || '-',
      unit: water.unit || 'm³',
      source: '能耗汇总接口',
      tone: 'blue',
      icon: 'water',
    },
    {
      key: 'total-output',
      stage: '折算',
      label: '综合折算',
      value: total.value || '-',
      unit: total.unit || 'kgce',
      source: '算法汇总',
      tone: 'result',
      emphasis: 'endpoint',
      icon: 'converter',
    },
    {
      key: 'per-ton-check',
      stage: '校核',
      label: '单吨能耗关注',
      value: maxPerTon ? `${maxPerTon.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxPerTon.value)}` : '待核',
      unit: 'kgce/吨',
      source: '能耗明细字段',
      tone: maxPerTon ? 'critical' : 'warning',
      emphasis: 'endpoint',
      icon: 'gauge',
    },
  ]
}

function buildEnergyStatusBar({
  targetDate = '',
  detailRows = [],
  runtimeState = {},
} = {}) {
  const syncState = resolveEnergySyncState({ detailRows, runtimeState })
  return {
    title: '能源中心',
    subtitle: '能耗看板',
    businessDate: targetDate,
    rowCount: Array.isArray(detailRows) ? detailRows.length : 0,
    updatedAt: resolveEnergyUpdatedAt(runtimeState),
    syncStatus: syncState.value,
    tone: syncState.tone,
  }
}

function buildEnergyEventRail({
  targetDate = '',
  detailRows = [],
  runtimeState = {},
} = {}) {
  const syncState = resolveEnergySyncState({ detailRows, runtimeState })
  const { errorText = '' } = runtimeState
  const rowCount = Array.isArray(detailRows) ? detailRows.length : 0
  const events = [
    {
      key: 'energy-sync',
      title: syncState.eventTitle,
      value: errorText || (rowCount > 0 ? `${rowCount} 条` : '待核'),
      time: targetDate,
      tone: syncState.tone,
    },
  ]
  const maxElectricity = findMaxEnergyRow(detailRows, 'electricity_value')
  const maxGas = findMaxEnergyRow(detailRows, 'gas_value')
  const maxWater = findMaxEnergyRow(detailRows, 'water_value')
  const maxOutput = findMaxEnergyRow(detailRows, 'output_weight')
  const maxPerTon = findMaxEnergyRow(detailRows, 'energy_per_ton')

  if (maxElectricity) {
    events.push({
      key: 'electricity-top',
      title: '电耗最高参考',
      value: `${maxElectricity.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxElectricity.value)} kWh`,
      time: maxElectricity.row?.business_date || targetDate,
      tone: 'warning',
    })
  }

  if (maxGas) {
    events.push({
      key: 'gas-top',
      title: '气耗最高参考',
      value: `${maxGas.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxGas.value)} m³`,
      time: maxGas.row?.business_date || targetDate,
      tone: 'warning',
    })
  }

  if (maxWater) {
    events.push({
      key: 'water-top',
      title: '水耗最高参考',
      value: `${maxWater.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxWater.value)} m³`,
      time: maxWater.row?.business_date || targetDate,
      tone: 'warning',
    })
  }

  if (maxOutput) {
    events.push({
      key: 'output-top',
      title: '产量口径参考',
      value: `${maxOutput.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxOutput.value)} 吨`,
      time: maxOutput.row?.business_date || targetDate,
      tone: 'success',
    })
  }

  if (maxPerTon) {
    events.push({
      key: 'per-ton-top',
      title: '单吨能耗关注',
      value: `${maxPerTon.row?.workshop_code || '未知车间'} ${formatEnergyNumber(maxPerTon.value)} kgce/吨`,
      time: maxPerTon.row?.business_date || targetDate,
      tone: 'warning',
    })
  }

  return events
}

function buildEnergyBottomStatus({
  detailRows = [],
  runtimeState = {},
} = {}) {
  const syncState = resolveEnergySyncState({ detailRows, runtimeState })
  const rowCount = Array.isArray(detailRows) ? detailRows.length : 0
  return [
    { key: 'system', label: '系统状态', value: syncState.value, tone: syncState.tone },
    { key: 'energy', label: '能耗明细', value: `${rowCount} 条`, tone: rowCount > 0 ? 'success' : 'warning' },
    { key: 'source', label: '数据来源', value: '能耗汇总接口', tone: rowCount > 0 ? 'success' : 'warning' },
    { key: 'updated-at', label: '页面刷新', value: resolveEnergyUpdatedAt(runtimeState), tone: syncState.tone },
  ]
}

function resolveLiveEnergySummary(aggregation = {}) {
  return aggregation.energy_summary || aggregation.energySummary || {}
}

function pickEnergyValue(source = {}, keys = []) {
  for (const key of keys) {
    if (source[key] === null || source[key] === undefined || source[key] === '') continue
    const value = toFiniteNumber(source[key])
    if (value !== null) return value
  }
  return null
}

function pickEnergyText(source = {}, keys = []) {
  for (const key of keys) {
    const value = source[key]
    if (value !== null && value !== undefined && String(value).trim()) return String(value).trim()
  }
  return ''
}

function formatLiveEnergyTime(value) {
  if (!value) return '--:--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--:--'
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function resolveLiveEnergySourceLabel(energy = {}) {
  const explicitLabel = pickEnergyText(energy, [
    'primary_source_label',
    'primarySourceLabel',
    'source_label',
    'sourceLabel',
  ])
  if (explicitLabel) return explicitLabel

  const source = pickEnergyText(energy, ['primary_source', 'primarySource', 'source'])
  if (source === 'iot_shadow') return '物联网采集'
  if (source === 'owner_only') return '电工填报'
  return '系统采集'
}

function buildLiveEnergyBottomStatus(aggregation = {}) {
  const energy = resolveLiveEnergySummary(aggregation)
  const usable = energy.data_available !== false && energy.dataAvailable !== false
  const algorithmEnergy = usable
    ? pickEnergyValue(energy, ['algorithm_total_energy', 'algorithmTotalEnergy', 'total_electricity', 'totalElectricity'])
    : null
  const ownerEnergy = pickEnergyValue(energy, [
    'owner_total_electricity',
    'ownerTotalElectricity',
    'owner_electricity',
    'ownerElectricity',
    'electricity_value',
    'electricityValue',
  ])
  const perTon = usable
    ? pickEnergyValue(energy, ['algorithm_energy_per_ton', 'algorithmEnergyPerTon', 'energy_per_ton', 'energyPerTon'])
    : null
  const sourceUpdatedAt = pickEnergyText(energy, [
    'source_updated_at',
    'sourceUpdatedAt',
    'primary_source_updated_at',
    'primarySourceUpdatedAt',
    'updated_at',
    'updatedAt',
  ])
  const ownerLabel = pickEnergyText(energy, ['owner_source_label', 'ownerSourceLabel']) || '电工填报'

  return [
    {
      key: 'energy-source',
      label: '能耗采集',
      value: algorithmEnergy !== null
        ? `${resolveLiveEnergySourceLabel(energy)} · ${formatLiveEnergyTime(sourceUpdatedAt)}`
        : '待同步',
      tone: algorithmEnergy !== null ? 'success' : 'warning',
    },
    {
      key: 'energy-fill',
      label: ownerLabel,
      value: ownerEnergy !== null ? `${formatEnergyNumber(ownerEnergy)} kWh` : '待填报',
      tone: ownerEnergy !== null ? 'success' : 'warning',
    },
    {
      key: 'energy-per-ton',
      label: '吨电耗',
      value: perTon !== null ? `${formatEnergyNumber(perTon)} kWh/吨` : (algorithmEnergy !== null ? '无产量分母' : '待同步'),
      tone: perTon !== null ? 'success' : 'warning',
    },
  ]
}

export function buildTodayStitchSurface({
  snapshotData = {},
  targetDate = '',
  liveAggregation = {},
  runtimeState = {},
} = {}) {
  const overview = snapshotData.daily_overview || {}
  const workshopTable = buildDailyWorkshopRows(overview.workshop_output || [])
  const missingReportRows = buildMissingReportRows(liveAggregation)

  return {
    stitch: STITCH_MANAGE_SCREENS.today,
    route: STITCH_MANAGE_SCREENS.today.route,
    businessDate: resolveBusinessDate(targetDate, snapshotData.business_date, overview.business_date),
    slotOrder: TODAY_STITCH_SLOT_ORDER,
    statusBar: {
      title: '工厂总览',
      subtitle: '昨日日报',
    },
    kpiStrip: buildDailySettlementCards(overview),
    comparisonRail: buildDailyComparisonCards(overview),
    productionFlow: workshopTable,
    workshopTable,
    wipDistribution: buildDailyWipRows(overview.wip_distribution || []),
    missingReportRows,
    eventRail: {
      kind: 'missing-report',
      rows: missingReportRows,
    },
    bottomStatus: buildTodayBottomStatus({ overview, liveAggregation, runtimeState }),
  }
}

export function buildLiveStitchSurface({
  aggregation = {},
  targetDate = '',
  streamStatus = 'idle',
  loadError = '',
} = {}) {
  const eventRail = buildLiveEventItems({ streamStatus, loadError, aggregation })
  const streamState = resolveStreamStatus(streamStatus)

  return {
    stitch: STITCH_MANAGE_SCREENS.live,
    route: STITCH_MANAGE_SCREENS.live.route,
    businessDate: resolveBusinessDate(targetDate, aggregation.business_date, aggregation.businessDate),
    slotOrder: LIVE_STITCH_SLOT_ORDER,
    statusBar: {
      title: '实时调度墙',
      streamStatus,
    },
    realtimeKpiStrip: buildLiveMetricCompareItems(aggregation),
    marketTicker: buildLiveTickerItems(aggregation),
    processFlow: buildLiveProcessFlowItems(aggregation),
    machineMatrix: buildLiveMachineMatrix(aggregation.workshops || []),
    mesDistribution: aggregation.wip_distribution || aggregation.wipDistribution || [],
    eventRail,
    priorityItems: buildLivePriorityItems(eventRail),
    drawer: {
      enabled: true,
    },
    bottomStatus: [
      { key: 'stream', label: '实时链路', value: streamState.value, tone: streamState.tone },
      { key: 'snapshot', label: '快照兜底', value: aggregation.business_date || aggregation.businessDate ? '可用' : '待核', tone: aggregation.business_date || aggregation.businessDate ? 'success' : 'warning' },
      ...buildLiveEnergyBottomStatus(aggregation),
    ],
  }
}

export function buildProductionStitchSurface({
  snapshotData = {},
  targetDate = '',
  kpiItems = [],
  rankedRows = [],
  productionBrief = [],
  leadingWorkshopText = '',
  sourceOverview = {},
  runtimeState = {},
} = {}) {
  return {
    stitch: STITCH_MANAGE_SCREENS.production,
    route: STITCH_MANAGE_SCREENS.production.route,
    businessDate: resolveBusinessDate(targetDate, snapshotData.business_date),
    slotOrder: PRODUCTION_STITCH_SLOT_ORDER,
    statusBar: {
      title: '生产分析',
      subtitle: '生产驾驶舱',
    },
    kpiStrip: kpiItems,
    sourceOverview,
    workshopRanking: rankedRows,
    productionBrief,
    signal: {
      text: leadingWorkshopText,
    },
    bottomStatus: buildProductionBottomStatus({ snapshotData, sourceOverview, runtimeState }),
  }
}

export function buildFillDetailsStitchSurface({
  targetDate = '',
  kpiItems = [],
  auditTicker = [],
  sourceChain = [],
  issueQueues = [],
  ledgerRows = [],
  filteredRows = [],
  runtimeState = {},
} = {}) {
  return {
    stitch: STITCH_MANAGE_SCREENS.fillDetails,
    route: STITCH_MANAGE_SCREENS.fillDetails.route,
    businessDate: resolveBusinessDate(targetDate),
    slotOrder: FILL_DETAILS_STITCH_SLOT_ORDER,
    statusBar: buildFillDetailsStatusBar({ targetDate, filteredRows, runtimeState }),
    kpiStrip: kpiItems,
    auditTicker,
    sourceChain,
    issueQueues,
    ledgerRows,
    filteredRows,
    bottomStatus: buildFillDetailsBottomStatus({ ledgerRows, filteredRows, runtimeState }),
    ledgerTools: {
      search: true,
      sourceFilter: true,
      workshopFilter: true,
    },
  }
}

export function buildEnergyStitchSurface({
  targetDate = '',
  kpiItems = [],
  detailRows = [],
  runtimeState = {},
} = {}) {
  return {
    stitch: STITCH_MANAGE_SCREENS.energy,
    route: STITCH_MANAGE_SCREENS.energy.route,
    businessDate: resolveBusinessDate(targetDate),
    slotOrder: ENERGY_STITCH_SLOT_ORDER,
    statusBar: buildEnergyStatusBar({ targetDate, detailRows, runtimeState }),
    kpiStrip: kpiItems,
    energyFlow: buildEnergyFlow({ kpiItems, detailRows }),
    detailRows,
    eventRail: buildEnergyEventRail({ targetDate, detailRows, runtimeState }),
    bottomStatus: buildEnergyBottomStatus({ detailRows, runtimeState }),
  }
}
