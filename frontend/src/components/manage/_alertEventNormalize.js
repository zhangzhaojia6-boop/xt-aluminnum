import {
  formatExceptionTypeLabel,
  formatQualityIssueTypeLabel,
  formatReconciliationTypeLabel
} from '../../utils/display.js'

const FD_ROUTE = '/manage/alerts?surface=anomaly'
const Q_ROUTE = '/manage/alerts?surface=quality'
const R_ROUTE = '/manage/alerts?surface=reconciliation'

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function joinNonEmpty(parts, sep = ' ') {
  return parts.map((p) => (p == null ? '' : String(p).trim())).filter(Boolean).join(sep)
}

function fallbackOccurredAt(row, targetDate) {
  return row.occurred_at || row.created_at || row.updated_at || `${targetDate}T00:00:00`
}

function fallbackStatus(row) {
  if (!row.status) return 'open'
  return row.status === 'resolved' ? 'resolved' : 'open'
}

function fallbackId(domain, row, idx, primary = 'id') {
  const raw = row[primary] ?? row.id ?? row.report_id ?? row.shift_id
  return raw != null ? `${domain}:${raw}` : `${domain}:${idx}`
}

function productionSummary(row) {
  if (row.summary) return row.summary
  const exception = row.exception_type ? formatExceptionTypeLabel(row.exception_type) : ''
  const shift = row.shift_name || row.shift_label
  const head = joinNonEmpty([row.workshop_name, shift, exception])
  const note = row.note ? String(row.note).trim() : ''
  if (head && note) return `${head}：${note}`
  return head || note || '生产异常'
}

function reportingSummary(row) {
  if (row.summary) return row.summary
  const reason = row.returned_reason ? String(row.returned_reason).trim() : ''
  const exception = row.exception_type ? formatExceptionTypeLabel(row.exception_type) : ''
  const shift = row.shift_name || row.shift_label
  const head = joinNonEmpty([row.workshop_name, shift])
  if (reason) return head ? `${head}：${reason}` : reason
  if (exception) return joinNonEmpty([head, exception])
  if (row.note) return joinNonEmpty([head, String(row.note).trim()], '：')
  return head || '上报异常'
}

function qualitySummary(row) {
  if (row.summary) return row.summary
  if (row.issue_desc) return String(row.issue_desc).trim()
  const type = row.issue_type ? formatQualityIssueTypeLabel(row.issue_type) : ''
  const dim = joinNonEmpty([row.dimension_key, row.field_name], ' · ')
  if (type && dim) return `${type}：${dim}`
  return type || dim || '质检异常'
}

function reconciliationSummary(row) {
  if (row.summary) return row.summary
  const type = row.reconciliation_type ? formatReconciliationTypeLabel(row.reconciliation_type) : ''
  const dim = row.dimension_key
  const a = row.source_a_value
  const b = row.source_b_value
  let diff = ''
  if (a != null || b != null) {
    diff = `${a ?? '-'} / ${b ?? '-'}`
  } else if (row.diff_value != null) {
    diff = `差 ${row.diff_value}`
  }
  return joinNonEmpty([type, dim, diff], '：') || '对账差异'
}

export function normalizeFactoryDirector(payload, targetDate) {
  const lane = payload && payload.exception_lane
  if (!lane) return []
  const out = []
  safeArray(lane.recent_items).forEach((row, idx) => {
    out.push({
      id: fallbackId('production', row, idx, 'report_id'),
      domain: 'production',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: productionSummary(row),
      detailRoute: FD_ROUTE,
      status: fallbackStatus(row)
    })
  })
  ;[...safeArray(lane.returned_items), ...safeArray(lane.reminder_items)].forEach((row, idx) => {
    out.push({
      id: fallbackId('reporting', row, idx, 'report_id'),
      domain: 'reporting',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: reportingSummary(row),
      detailRoute: FD_ROUTE,
      status: fallbackStatus(row)
    })
  })
  return out
}

export function normalizeQuality(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('quality', row, idx),
    domain: 'quality',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: qualitySummary(row),
    detailRoute: Q_ROUTE,
    status: fallbackStatus(row)
  }))
}

export function normalizeReconciliation(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('reconciliation', row, idx),
    domain: 'reconciliation',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: reconciliationSummary(row),
    detailRoute: R_ROUTE,
    status: fallbackStatus(row)
  }))
}

export function mergeAndSort(eventsArrays) {
  const merged = eventsArrays.flat()
  return merged.sort((a, b) => {
    if (a.occurredAt !== b.occurredAt) return a.occurredAt < b.occurredAt ? 1 : -1
    return a.domain < b.domain ? -1 : a.domain > b.domain ? 1 : 0
  })
}
