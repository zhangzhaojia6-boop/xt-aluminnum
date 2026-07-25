import { filterActiveWorkshopRows, isRetiredWorkshopName } from './activeWorkshops.js'

export const MISSING_DAILY_VALUE = '暂无可信数据'

const TRUSTED_FACT_SOURCES = {
  total_output_daily: new Set([
    'dingtalk_supplement',
    'root_owner_correction',
    'mes_packaging_output',
    'mes_verified',
  ]),
  finished_inbound_daily: new Set([
    'dingtalk_supplement',
    'root_owner_correction',
    'finished_inbound_output',
    'wms_direct',
    'mes_stock_header_records',
    'mes_stock_records',
  ]),
  wip_total: new Set([
    'dingtalk_supplement',
    'root_owner_correction',
    'mes_wip_distribution',
    'mes_coil_snapshot_business_date',
    'mes_daily_wip_snapshot',
    'mes_wip_total_snapshot',
  ]),
  total_electricity_kwh: new Set([
    'dingtalk_supplement',
    'root_owner_correction',
    'iot_energy',
    'owner_daily',
    'owner_or_energy_summary',
    'data_hub_manual',
  ]),
  daily_yield_rate: new Set([
    'dingtalk_supplement',
    'root_owner_correction',
    'owner_daily',
    'quality_yield_daily',
    'computed_same_basis',
  ]),
}

function normalizeFactSource(value) {
  if (typeof value !== 'string' || !value.trim()) return ''
  return value
    .trim()
    .toLowerCase()
    .replace(/[ /-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}

export function safeFactSource(value, field) {
  const normalized = normalizeFactSource(value)
  const allowed = TRUSTED_FACT_SOURCES[field]
  if (!normalized || !allowed?.has(normalized)) return null
  return value.trim()
}

export function openFactTrace(router, traceId) {
  const trace = typeof traceId === 'string' ? traceId.trim() : ''
  if (!trace || typeof router?.push !== 'function') return false
  router.push({ path: '/manage/alerts', query: { trace_id: trace } })
  return true
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function formatNumber(value, digits = 2) {
  const numeric = toNumber(value)
  if (numeric === null) return MISSING_DAILY_VALUE
  return numeric.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function formatMetric(value, unit = '', digits = 2) {
  const text = formatNumber(value, digits)
  if (text === MISSING_DAILY_VALUE) return text
  return unit ? `${text} ${unit}` : text
}

function formatPlainMetric(value, digits = 2) {
  const numeric = toNumber(value)
  if (numeric === null) return MISSING_DAILY_VALUE
  return numeric.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function isEnergyAvailable(energy = {}) {
  if (energy.data_available === false) return false
  return toNumber(energy.total_electricity) !== null
    || toNumber(energy.total_energy) !== null
    || toNumber(energy.algorithm_total_energy) !== null
    || toNumber(energy.total_gas) !== null
    || toNumber(energy.energy_per_ton) !== null
}

function pickEnergyValue(energy = {}, keys = []) {
  for (const key of keys) {
    const value = toNumber(energy[key])
    if (value !== null) return value
  }
  return null
}

function sumWorkshopOutput(rows = []) {
  const workshopRows = buildDailyWorkshopRows(rows)
  if (!workshopRows.length) return null
  return workshopRows.reduce((sum, row) => sum + (toNumber(row.daily_output) || 0), 0)
}

function rawWorkshopName(row = {}) {
  return String(row.workshop || row.workshop_name || row.workshopName || row.name || '').trim()
}

function filterVisibleWipRows(rows = []) {
  return (rows || []).filter((row) => {
    const name = rawWorkshopName(row)
    if (!name || isRetiredWorkshopName(name)) return false
    if (row.is_active === false || row.is_removed === true || row.removed === true) return false
    const status = String(row.status || row.workshop_status || '').toLowerCase()
    return status !== 'removed'
  })
}

export function buildDailySettlementCards(overview = {}, factClosure) {
  const plantOutput = overview.plant_output || {}
  const contracts = overview.contracts || {}
  const energy = overview.energy || {}
  const yieldRates = overview.yield_rates || {}
  const hasEnergy = isEnergyAvailable(energy)
  const processThroughput = sumWorkshopOutput(overview.workshop_output || [])

  const cards = [
    {
      key: 'feeding-input',
      label: '投料量',
      sourceLabel: 'MES投料',
      value: formatPlainMetric(plantOutput.factory_feeding_daily_input),
      unit: plantOutput.factory_feeding_daily_input == null ? '' : '吨',
      tone: plantOutput.factory_feeding_daily_input == null ? 'muted' : 'primary',
      status: plantOutput.factory_feeding_daily_input == null ? 'muted' : null,
    },
    {
      key: 'plant-output',
      label: '包装产量',
      value: formatPlainMetric(plantOutput.daily_output),
      unit: '吨',
      deltaText: plantOutput.yesterday_output == null ? null : `比昨日 ${formatPlainMetric((toNumber(plantOutput.daily_output) || 0) - (toNumber(plantOutput.yesterday_output) || 0))} 吨`,
      tone: 'success',
    },
    {
      key: 'finished-inbound',
      label: '全厂入库产量',
      value: formatPlainMetric(plantOutput.finished_inbound_output),
      unit: plantOutput.finished_inbound_output == null ? '' : '吨',
      tone: plantOutput.finished_inbound_output == null ? 'muted' : 'success',
      status: plantOutput.finished_inbound_output == null ? 'muted' : null,
    },
    {
      key: 'process-throughput',
      label: '过站下机参考',
      value: formatPlainMetric(processThroughput),
      unit: processThroughput == null ? '' : '吨',
      tone: processThroughput == null ? 'muted' : 'primary',
      status: processThroughput == null ? 'muted' : null,
    },
    {
      key: 'contract-tonnage',
      label: '合同吨数',
      value: formatPlainMetric(contracts.daily_new),
      unit: contracts.unit || '吨',
      tone: 'primary',
    },
    {
      key: 'energy-per-ton',
      label: '吨电耗',
      value: hasEnergy ? formatPlainMetric(plantOutput.energy_per_ton ?? energy.energy_per_ton, 1) : MISSING_DAILY_VALUE,
      unit: hasEnergy ? 'kWh/吨' : '',
      tone: hasEnergy ? 'warning' : 'muted',
      status: hasEnergy ? null : 'muted',
    },
    {
      key: 'yield-rate',
      label: '全厂成品率',
      value: formatPlainMetric(plantOutput.yield_rate ?? yieldRates.daily),
      unit: (plantOutput.yield_rate ?? yieldRates.daily) == null ? '' : '%',
      tone: 'primary',
    },
  ]

  if (arguments.length < 2) return cards

  const facts = new Map(
    buildFactClosureSurface(factClosure).criticalFields.map((field) => [field.key, field])
  )
  const fieldByCard = {
    'plant-output': 'total_output_daily',
    'finished-inbound': 'finished_inbound_daily',
    'yield-rate': 'daily_yield_rate',
  }
  return cards.map((card) => {
    const fieldName = fieldByCard[card.key]
    if (!fieldName) return card
    const fact = facts.get(fieldName) || {
      value: null,
      unit: null,
      status: 'missing',
      source: '暂无可信来源',
    }
    const numeric = toNumber(fact.value)
    const confirmed = fact.status === 'confirmed' && numeric !== null
    const { deltaText: _deltaText, deltaTone: _deltaTone, ...baseCard } = card
    return {
      ...baseCard,
      value: confirmed ? formatPlainMetric(numeric) : '--',
      unit: fact.unit || '',
      status: confirmed ? 'confirmed' : (fact.status === 'confirmed' ? 'missing' : fact.status || 'missing'),
      sourceLabel: fact.source || '暂无可信来源',
      tone: confirmed ? card.tone : 'muted',
    }
  })
}

export function buildDailyComparisonCards(overview = {}) {
  const energy = overview.energy || {}
  const yieldRates = overview.yield_rates || {}
  const plantOutput = overview.plant_output || {}
  const hasEnergy = isEnergyAvailable(energy)
  const algorithmElectricity = pickEnergyValue(energy, ['total_electricity', 'algorithm_total_energy'])
  const ownerElectricity = pickEnergyValue(energy, ['owner_electricity', 'owner_total_electricity', 'electricity_value'])

  return [
    {
      key: 'energy',
      title: '算法能耗',
      primaryLabel: '算法',
      primaryValue: hasEnergy && algorithmElectricity !== null ? formatMetric(algorithmElectricity, '度') : MISSING_DAILY_VALUE,
      compareLabel: '电工填报',
      compareValue: formatMetric(ownerElectricity, '度'),
      tone: hasEnergy ? 'warning' : 'muted',
    },
    {
      key: 'yield',
      title: '全厂成品率',
      primaryLabel: '成品入库',
      primaryValue: formatMetric(plantOutput.finished_inbound_output, '吨'),
      compareLabel: '投料量',
      compareValue: formatMetric(plantOutput.factory_feeding_daily_input, '吨'),
      value: formatMetric(plantOutput.yield_rate ?? yieldRates.daily, '%'),
      tone: (plantOutput.yield_rate ?? yieldRates.daily) == null ? 'muted' : 'primary',
    },
  ]
}

export function buildDailyWorkshopRows(rows = []) {
  return filterActiveWorkshopRows(rows)
    .map((row, index) => ({
      ...row,
      key: row.workshop_id ?? row.workshop ?? index,
      workshop: row.workshop || row.workshop_name || '--',
      dailyOutputText: formatMetric(row.daily_output, '吨'),
      monthlyOutputText: formatMetric(row.monthly_output, '吨'),
      deltaText: row.delta == null ? '—' : formatMetric(row.delta, '吨'),
      dailyValue: toNumber(row.daily_output) || 0,
    }))
    .sort((a, b) => b.dailyValue - a.dailyValue)
}

export function buildDailyWipRows(rows = []) {
  return filterVisibleWipRows(rows)
    .map((row, index) => {
      const title = rawWorkshopName(row) || '--'
      const feedingText = formatMetric(row.feeding_weight, '吨')
      const totalWeight = toNumber(row.total_weight)
      return {
        key: `${title}-${index}`,
        title,
        weightText: formatMetric(row.total_weight, '吨'),
        totalWeight: totalWeight ?? 0,
        feedingText: feedingText === MISSING_DAILY_VALUE ? '投料 —' : `投料 ${feedingText}`,
        countText: `${toNumber(row.coil_count) ?? 0} 卷`,
        sourceLabel: row.source_label || '外部 MES 当日快照参考',
      }
    })
}

export function buildFactActionSummary(factMissing) {
  const rows = Array.isArray(factMissing)
    ? factMissing.filter((item) => item && typeof item === 'object' && !Array.isArray(item))
    : []
  const openRows = rows.filter((item) => (
    String(item.status || item.task_status || item.taskStatus || '').toLowerCase() !== 'resolved'
  ))
  const valueFor = (item, snakeKey, camelKey) => item[snakeKey] ?? item[camelKey]
  const actionableRows = openRows.filter((item) => (
    String(valueFor(item, 'action_route', 'actionRoute') || '').startsWith('/entry/fill')
  ))

  return {
    openCount: openRows.length,
    actionableCount: actionableRows.length,
    notifiedCount: actionableRows.filter((item) => (
      String(valueFor(item, 'delivery_status', 'deliveryStatus') || '').toLowerCase() === 'sent'
    )).length,
    sourceRecheckCount: openRows.filter((item) => (
      valueFor(item, 'fill_strategy', 'fillStrategy') === 'source_recheck'
    )).length,
    dependencyCount: openRows.filter((item) => (
      valueFor(item, 'fill_strategy', 'fillStrategy') === 'dependency_fill'
    )).length,
  }
}

export function buildFactClosureSurface(factClosure) {
  const fields = Array.isArray(factClosure?.critical_fields)
    ? factClosure.critical_fields
    : []
  const validFields = fields.filter((field) => (
    field
    && typeof field === 'object'
    && !Array.isArray(field)
    && typeof field.field === 'string'
    && field.field.trim()
  ))

  return {
    status: factClosure?.status || 'unknown',
    blockedCount: validFields.filter((field) => field.status !== 'confirmed').length,
    criticalFields: validFields.map((field) => ({
      key: field.field,
      value: Object.prototype.hasOwnProperty.call(field, 'value') ? field.value : null,
      unit: typeof field.unit === 'string' ? field.unit : null,
      status: typeof field.status === 'string' && field.status ? field.status : 'missing',
      source: safeFactSource(field.source, field.field) || '暂无可信来源',
      businessWindow: typeof field.business_window === 'string' ? field.business_window : null,
      action: typeof field.action === 'string' && field.action ? field.action : '等待鑫泰铝业智能大脑追踪',
      traceId: typeof field.trace_id === 'string' ? field.trace_id : '',
    })),
  }
}
