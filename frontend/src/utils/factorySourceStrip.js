import { sourceLabel } from './factoryCommandFormatters.js'

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function formatValue(value, digits = 2) {
  const numeric = toNumber(value)
  if (numeric === null) return '—'
  return numeric.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function sourceTone(source, status) {
  if (status === 'fresh') return 'success'
  if (source === 'local_shift_data' || ['stale', 'idle', 'unconfigured'].includes(status)) return 'warning'
  if (['failed', 'migration_missing', 'offline_or_blocked'].includes(status)) return 'danger'
  return 'normal'
}

export function buildFactorySourceStrip(overview = {}) {
  const freshness = overview.freshness || {}
  const source = String(overview.source || freshness.source || 'unknown')
  const status = String(freshness.status || '')
  const processOutput = overview.process_output_tons ?? overview.total_output_tons
  return {
    source,
    status,
    sourceLabel: sourceLabel(source),
    tone: sourceTone(source, status),
    items: [
      { key: 'inbound', label: 'MES包装产量', value: formatValue(overview.today_output_tons), unit: '吨' },
      { key: 'process', label: '过站下机参考', value: formatValue(processOutput), unit: '吨' },
      { key: 'wip', label: '在制', value: formatValue(overview.wip_tons), unit: '吨' },
      { key: 'yield', label: '成品率', value: formatValue(overview.yield_rate), unit: '%' },
    ],
  }
}
