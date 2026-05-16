const DIMENSION_LABELS = {
  workshop: '车间',
  workshop_name: '车间',
  shift: '班次',
  shift_name: '班次',
  team: '班组',
  team_name: '班组',
  machine: '机列',
  machine_id: '机列',
  machine_line: '机列',
  tracking_card_no: '跟踪卡',
}

const FIELD_LABELS = {
  output_weight: '产出重量',
  input_weight: '投入重量',
  headcount: '人数',
  energy_total: '能耗',
}

const SOURCE_LABELS = {
  attendance_results: '考勤',
  production: '填报端产量',
  shift_production_data: '填报端产量',
  mes: '外部 MES',
  mes_export: '外部 MES',
  energy: '能耗',
}

function normalizeDimensionValue(value) {
  return value && value !== 'None' && value !== 'null' ? value : ''
}

export function parseReconciliationDimension(value) {
  const result = { workshop: '', shift: '' }
  for (const part of String(value || '').split('|')) {
    const separatorIndex = part.indexOf(':')
    if (separatorIndex === -1) continue
    const key = part.slice(0, separatorIndex)
    const rawValue = part.slice(separatorIndex + 1)
    const text = normalizeDimensionValue(rawValue)
    if (key === 'workshop' || key === 'workshop_name') result.workshop = text
    if (key === 'shift' || key === 'shift_name') result.shift = text
  }
  return result
}

export function formatReconciliationDimension(value) {
  const text = String(value || '').trim()
  if (!text) return '-'
  if (!text.includes(':')) return text

  const parts = text
    .split('|')
    .map((part) => {
      const separatorIndex = part.indexOf(':')
      if (separatorIndex === -1) return ''
      const key = part.slice(0, separatorIndex)
      const rawValue = part.slice(separatorIndex + 1)
      const normalizedValue = normalizeDimensionValue(rawValue)
      if (!normalizedValue) return ''
      return `${DIMENSION_LABELS[key] || key} ${normalizedValue}`
    })
    .filter(Boolean)

  return parts.length ? parts.join(' / ') : text
}

export function formatReconciliationFieldLabel(fieldName) {
  return FIELD_LABELS[fieldName] || fieldName || '-'
}

export function formatReconciliationSourceLabel(source) {
  return SOURCE_LABELS[source] || source || '-'
}

export function reconciliationFieldUnit(fieldName) {
  const value = String(fieldName || '').toLowerCase()
  if (value === 'output_weight' || value === 'input_weight') return ' 吨'
  if (String(fieldName || '').includes('重量')) return ' 吨'
  if (value === 'headcount' || String(fieldName || '').includes('人数')) return ' 人'
  if (value === 'energy_total' || String(fieldName || '').includes('能耗')) return ' kWh'
  return ''
}

export function formatReconciliationValue(value, fieldName) {
  const formatted = formatCompactNumber(value)
  if (formatted === '-') return formatted
  return `${formatted}${reconciliationFieldUnit(fieldName)}`
}

export function formatReconciliationDiffValue(item = {}, options = {}) {
  const currentItem = item || {}
  const formatted = formatCompactNumber(currentItem.diff_value)
  if (formatted === '-') return formatted
  const diff = Number(currentItem.diff_value)
  const sign = Number.isNaN(diff) || diff <= 0 ? '' : '+'
  return `${options.prefix || ''}${sign}${formatted}${reconciliationFieldUnit(currentItem.field_name)}`
}

function formatCompactNumber(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  if (Number.isNaN(number)) return String(value)
  return number.toFixed(3).replace(/\.?0+$/, '')
}
