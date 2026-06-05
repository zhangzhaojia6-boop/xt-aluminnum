export const MISSING_DAILY_VALUE = '暂无可信数据'

const REMOVED_WORKSHOP_NAMES = new Set(['冷轧三车间', '二分厂精整车间'])

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

export function buildDailySettlementCards(overview = {}) {
  const plantOutput = overview.plant_output || {}
  const contracts = overview.contracts || {}
  const energy = overview.energy || {}
  const yieldRates = overview.yield_rates || {}
  const hasEnergy = isEnergyAvailable(energy)
  const processThroughput = sumWorkshopOutput(overview.workshop_output || [])

  return [
    {
      key: 'plant-output',
      label: '全厂入库产量',
      value: formatPlainMetric(plantOutput.daily_output),
      unit: '吨',
      deltaText: plantOutput.yesterday_output == null ? null : `比昨日 ${formatPlainMetric((toNumber(plantOutput.daily_output) || 0) - (toNumber(plantOutput.yesterday_output) || 0))} 吨`,
      tone: 'success',
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
      label: '日成品率',
      value: formatPlainMetric(yieldRates.daily),
      unit: yieldRates.daily == null ? '' : '%',
      tone: 'primary',
    },
    {
      key: 'energy-cost',
      label: '能耗成本',
      value: hasEnergy ? formatPlainMetric(energy.total_cost) : MISSING_DAILY_VALUE,
      unit: hasEnergy && energy.total_cost != null ? '万元' : '',
      tone: hasEnergy ? 'warning' : 'muted',
      status: hasEnergy ? null : 'muted',
    },
  ]
}

export function buildDailyComparisonCards(overview = {}) {
  const energy = overview.energy || {}
  const yieldRates = overview.yield_rates || {}
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
      title: '算法成品率',
      primaryLabel: '算法',
      primaryValue: formatMetric(yieldRates.daily, '%'),
      compareLabel: '内勤对照',
      compareValue: formatMetric(yieldRates.owner_daily, '%'),
      tone: yieldRates.daily == null ? 'muted' : 'primary',
    },
  ]
}

function isRemovedWorkshop(row = {}) {
  const name = String(row.workshop || row.workshop_name || '').trim()
  const status = String(row.status || row.workshop_status || '').toLowerCase()
  return row.is_active === false
    || row.is_removed === true
    || row.removed === true
    || status === 'removed'
    || REMOVED_WORKSHOP_NAMES.has(name)
}

export function buildDailyWorkshopRows(rows = []) {
  return (rows || [])
    .filter((row) => !isRemovedWorkshop(row))
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
  return (rows || [])
    .filter((row) => !isRemovedWorkshop(row))
    .map((row, index) => {
      const feedingText = formatMetric(row.feeding_weight, '吨')
      return {
        key: row.workshop ?? index,
        title: row.workshop || '--',
        weightText: formatMetric(row.total_weight, '吨'),
        feedingText: feedingText === MISSING_DAILY_VALUE ? '投料 —' : `投料 ${feedingText}`,
        countText: `${toNumber(row.coil_count) ?? 0} 卷`,
        sourceLabel: row.source_label || '外部 MES 当日快照参考',
      }
    })
}
