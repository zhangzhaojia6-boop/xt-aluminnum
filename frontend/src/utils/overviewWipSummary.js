const SOURCE_LABELS = {
  mes_projection: 'MES 投影',
  mes_extended: 'MES 扩展数据',
  local_shift_data: '本地填报',
  unavailable: '未接入',
}

const FRESHNESS_LABELS = {
  stale: 'MES 滞后',
  failed: '同步失败',
  unconfigured: '未配置',
  migration_missing: '投影未就绪',
  idle: '未同步',
  offline_or_blocked: '离线/阻塞',
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatTonLabel(value) {
  const number = toFiniteNumber(value)
  if (number === null) return '--'
  return `${Math.round(number * 100) / 100} t`
}

function sourceLabel(source, status) {
  if (source === 'local_shift_data') return SOURCE_LABELS.local_shift_data
  if (source === 'unavailable') return FRESHNESS_LABELS[status] || SOURCE_LABELS.unavailable
  return FRESHNESS_LABELS[status] || SOURCE_LABELS[source] || '未知来源'
}

function sourceTone(source, status) {
  if (source === 'local_shift_data') return 'warning'
  if (status === 'fresh') return 'success'
  if (['failed', 'offline_or_blocked', 'migration_missing'].includes(status) || source === 'unavailable') return 'danger'
  if (['stale', 'unconfigured', 'idle'].includes(status)) return 'warning'
  return 'normal'
}

export function buildOverviewWipSummary(factoryCommand = {}, dashboard = {}) {
  const freshness = factoryCommand.freshness || dashboard.mes_sync_status || {}
  const status = String(freshness.status || '').toLowerCase()
  const source = String(
    factoryCommand.source || freshness.source || (status ? 'mes_projection' : 'unavailable'),
  ).trim() || 'unavailable'

  return {
    source,
    freshnessStatus: status || 'unknown',
    wipTotalTonLabel: formatTonLabel(factoryCommand.wip_tons),
    dailyOutputTonLabel: formatTonLabel(factoryCommand.today_output_tons ?? factoryCommand.total_output_tons),
    sourceLabel: sourceLabel(source, status),
    sourceTone: sourceTone(source, status),
  }
}
