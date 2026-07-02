import { filterActiveWorkshopRows, isRetiredWorkshopName } from './activeWorkshops.js'

export const MISSING_DAILY_VALUE = '暂无可信数据'

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

export function buildDailySettlementCards(overview = {}) {
  const plantOutput = overview.plant_output || {}
  const contracts = overview.contracts || {}
  const energy = overview.energy || {}
  const yieldRates = overview.yield_rates || {}
  const hasEnergy = isEnergyAvailable(energy)
  const processThroughput = sumWorkshopOutput(overview.workshop_output || [])

  return [
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
      sourceLabel: '包装工序',
      value: formatPlainMetric(plantOutput.daily_output),
      unit: '吨',
      deltaText: plantOutput.yesterday_output == null ? null : `比昨日 ${formatPlainMetric((toNumber(plantOutput.daily_output) || 0) - (toNumber(plantOutput.yesterday_output) || 0))} 吨`,
      tone: 'success',
    },
    {
      key: 'finished-inbound',
      label: '全厂入库产量',
      sourceLabel: '成品入库',
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
      sourceLabel: '投料入库',
      value: formatPlainMetric(plantOutput.yield_rate ?? yieldRates.daily),
      unit: (plantOutput.yield_rate ?? yieldRates.daily) == null ? '' : '%',
      tone: 'primary',
    },
  ]
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

export function buildFactClosureSurface(factClosure) {
  const fields = Array.isArray(factClosure?.critical_fields)
    ? factClosure.critical_fields
    : []

  return {
    status: factClosure?.status || 'unknown',
    blockedCount: fields.filter((field) => field.status !== 'confirmed').length,
    criticalFields: fields.map((field) => ({
      key: field.field,
      status: field.status,
      source: field.source || '暂无可信来源',
      action: field.action || '等待鑫泰铝业智能大脑追踪',
      traceId: field.trace_id || '',
    })),
  }
}
