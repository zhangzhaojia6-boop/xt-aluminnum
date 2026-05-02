import { formatNumber } from './display'

export function numberValue(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num : 0
}

export function formatWeight(value) {
  return formatNumber(value ?? 0, 2)
}

export function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '--'
  return `${formatNumber(value, 2)}%`
}

export function yieldToneClass(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return 'is-yield-neutral'
  if (num >= 97) return 'is-yield-good'
  if (num >= 94) return 'is-yield-warn'
  return 'is-yield-danger'
}

export function submissionSymbol(status) {
  if (status === 'not_applicable') return '—'
  if (status === 'all_submitted') return '✓'
  if (status === 'in_progress') return '⏳'
  return '○'
}

export function formatAttendance(shift) {
  if (!shift.is_applicable || shift.attendance_status === 'not_applicable') return '—'
  const exceptionCount = numberValue(shift.attendance_exception_count)
  if (shift.attendance_status === 'confirmed' && exceptionCount === 0) return '✓ 已确认'
  if (exceptionCount > 0) return `⚠ ${exceptionCount} 人异常`
  if (shift.attendance_status === 'pending') return '⏳ 待确认'
  return '○ 未开始'
}

export function formatEntryStatus(status) {
  if (status === 'submitted') return '已提交'
  if (status === 'verified') return '已核对'
  if (status === 'approved') return '已通过系统校验'
  if (status === 'synced') return 'MES 已同步'
  return '草稿'
}

export function formatEntryType(type) {
  if (type === 'mes_projection') return 'MES 投影'
  return type === 'completed' ? '本班完工' : '接续生产'
}
