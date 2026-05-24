const FD_LEGACY = '/manage/alerts/legacy?surface=anomaly'
const Q_LEGACY = '/manage/alerts/legacy?surface=quality'
const R_LEGACY = '/manage/alerts/legacy?surface=reconciliation'

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function fallbackOccurredAt(row, targetDate) {
  return row.occurred_at || row.created_at || `${targetDate}T00:00:00`
}

function fallbackSummary(row) {
  if (row.summary) return row.summary
  return [row.workshop_name, row.shift_label, row.event_type].filter(Boolean).join(' ')
}

function fallbackId(domain, row, idx) {
  const raw = row.id ?? row.shift_id
  return raw != null ? `${domain}:${raw}` : `${domain}:${idx}`
}

function fallbackStatus(row) {
  if (!row.status) return 'open'
  return row.status === 'resolved' ? 'resolved' : 'open'
}

export function normalizeFactoryDirector(payload, targetDate) {
  const lane = payload && payload.exception_lane
  if (!lane) return []
  const out = []
  safeArray(lane.recent_items).forEach((row, idx) => {
    out.push({
      id: fallbackId('production', row, idx),
      domain: 'production',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: fallbackSummary(row),
      detailRoute: FD_LEGACY,
      status: fallbackStatus(row)
    })
  })
  ;[...safeArray(lane.returned_items), ...safeArray(lane.reminder_items)].forEach((row, idx) => {
    out.push({
      id: fallbackId('reporting', row, idx),
      domain: 'reporting',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: fallbackSummary(row),
      detailRoute: FD_LEGACY,
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
    summary: fallbackSummary(row),
    detailRoute: Q_LEGACY,
    status: fallbackStatus(row)
  }))
}

export function normalizeReconciliation(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('reconciliation', row, idx),
    domain: 'reconciliation',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: fallbackSummary(row),
    detailRoute: R_LEGACY,
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
