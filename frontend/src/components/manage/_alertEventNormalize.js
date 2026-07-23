import {
  formatExceptionTypeLabel,
  formatQualityIssueTypeLabel,
  formatReconciliationTypeLabel,
  formatShiftLabel
} from '../../utils/display.js'
import { safeFactSource } from '../../utils/manageDailyReportSurface.js'

const FD_ROUTE = '/manage/alerts?surface=anomaly'
const Q_ROUTE = '/manage/alerts?surface=quality'
const R_ROUTE = '/manage/alerts?surface=reconciliation'
const MES_ROUTE = '/manage/fill-details'
const REPORTING_ROUTE = '/manage/fill-details'

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function joinNonEmpty(parts, sep = ' ') {
  return parts.map((p) => (p == null ? '' : String(p).trim())).filter(Boolean).join(sep)
}

function actionGroupKey(domain, parts) {
  const normalized = parts.map((part) => String(part ?? '').trim() || '_')
  return `${domain}:${normalized.join('|')}`
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
  const shift = formatShiftLabel(row.shift_name || row.shift_label, '')
  const head = joinNonEmpty([row.workshop_name, shift, exception])
  const note = row.note ? String(row.note).trim() : ''
  if (head && note) return `${head}：${note}`
  return head || note || '生产异常'
}

function reportingSummary(row) {
  if (row.summary) return row.summary
  const reason = row.returned_reason ? String(row.returned_reason).trim() : ''
  const exception = row.exception_type ? formatExceptionTypeLabel(row.exception_type) : ''
  const shift = formatShiftLabel(row.shift_name || row.shift_label, '')
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

function productionDetail(row) {
  return joinNonEmpty([
    row.note,
    row.exception_desc,
    row.machine_name,
    row.tracking_card_no,
    row.reporter_name,
  ], ' · ')
}

function reportingDetail(row) {
  return joinNonEmpty([
    row.returned_reason,
    row.note,
    row.machine_name,
    row.tracking_card_no,
    row.created_by_user_name,
  ], ' · ')
}

function qualityDetail(row) {
  return joinNonEmpty([
    row.issue_type,
    row.dimension_key,
    row.field_name,
    row.status,
  ], ' · ')
}

function reconciliationDetail(row) {
  return joinNonEmpty([
    row.reconciliation_type,
    row.dimension_key,
    row.source_a_name,
    row.source_b_name,
    row.source_a_value != null || row.source_b_value != null ? `${row.source_a_value ?? '-'} / ${row.source_b_value ?? '-'}` : '',
  ], ' · ')
}

function mesGapLabel(status) {
  if (status === 'missing_local_entry') return 'MES有工序本地未填'
  if (status === 'mes_batch_unmapped') return 'MES批号未映射随行卡'
  if (status === 'local_entry_unassigned') return '本地填报未归属机列'
  if (status === 'weight_mismatch') return 'MES与本地重量不一致'
  return 'MES填报链路待核'
}

function mesGapSummary(row) {
  return `${mesGapLabel(row.status)}：${joinNonEmpty([
    row.workshop_name,
    row.mes_machine_name || row.local_machine_name,
    row.shift_name,
  ], ' · ')}`
}

function mesGapDetail(row) {
  return joinNonEmpty([
    row.tracking_card_no,
    row.batch_no,
    row.process_name,
    row.shift_window,
    row.mes_output_weight != null ? `MES ${row.mes_output_weight} kg` : '',
    row.local_output_weight != null ? `本地 ${row.local_output_weight} kg` : '',
  ], ' · ')
}

function numberValue(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function statusIsMissing(status) {
  return !['submitted', 'approved', 'auto_confirmed', 'confirmed', '已填', '已提交'].includes(String(status || '').toLowerCase())
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
      detail: productionDetail(row),
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
      detail: reportingDetail(row),
      detailRoute: FD_ROUTE,
      status: fallbackStatus(row)
    })
  })
  return out
}

export function normalizeQuality(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('quality', row, idx),
    groupKey: row.issue_type || row.dimension_key || row.field_name
      ? actionGroupKey('quality', [
          row.issue_type,
          row.issue_level,
          row.dimension_key,
          row.field_name,
          row.status,
        ])
      : undefined,
    domain: 'quality',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: qualitySummary(row),
    detail: qualityDetail(row),
    detailRoute: Q_ROUTE,
    status: fallbackStatus(row)
  }))
}

export function normalizeReconciliation(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('reconciliation', row, idx),
    groupKey: row.reconciliation_type || row.dimension_key || row.field_name
      ? actionGroupKey('reconciliation', [
          row.reconciliation_type,
          row.dimension_key,
          row.field_name,
          row.source_a,
          row.source_b,
          row.status,
        ])
      : undefined,
    domain: 'reconciliation',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: reconciliationSummary(row),
    detail: reconciliationDetail(row),
    detailRoute: R_ROUTE,
    status: fallbackStatus(row)
  }))
}

export function normalizeMesFillGaps(payload, targetDate) {
  return safeArray(payload?.items || payload)
    .filter((row) => row?.status && row.status !== 'matched')
    .map((row, idx) => ({
      id: `mes-fill-gap:${row.tracking_card_no || row.batch_no || row.local_entry_id || idx}`,
      groupKey: row.workshop_id || row.workshop_name || row.mes_resolved_machine_id
        || row.mes_machine_name || row.local_machine_name || row.shift_name || row.process_name
        ? actionGroupKey('mes', [
            row.status,
            row.workshop_id || row.workshop_name,
            row.mes_resolved_machine_id || row.mes_machine_name || row.local_machine_name,
            row.shift_name,
            row.process_name,
          ])
        : undefined,
      domain: 'mes',
      occurredAt: row.mes_end_time || fallbackOccurredAt(row, targetDate),
      summary: mesGapSummary(row),
      detail: mesGapDetail(row),
      detailRoute: MES_ROUTE,
      status: 'open'
    }))
}

export function normalizeLiveMissingReports(payload, targetDate) {
  const progress = payload?.overall_progress || payload?.overallProgress || {}
  const pending = progress.pending_assignment || progress.pendingAssignment || {}
  const ownerStatus = payload?.owner_daily_status || payload?.ownerDailyStatus || {}
  const out = []
  const missingCellCount = numberValue(progress.missing_cell_count ?? progress.missingCellCount)
  const pendingCount = numberValue(pending.entry_count ?? pending.entryCount)
  const missingMachineCount = numberValue(pending.missing_machine_count ?? pending.missingMachineCount)
  const missingShiftCount = numberValue(pending.missing_shift_count ?? pending.missingShiftCount)

  if (missingCellCount > 0) {
    out.push({
      id: 'live-missing:missing-cells',
      domain: 'reporting',
      occurredAt: `${targetDate}T23:59:59`,
      summary: `缺报 ${missingCellCount} 个填报单元`,
      detail: joinNonEmpty([
        pendingCount > 0 ? `待归属 ${pendingCount} 条` : '',
        missingMachineCount > 0 ? `缺机列 ${missingMachineCount} 条` : '',
        missingShiftCount > 0 ? `缺班次 ${missingShiftCount} 条` : '',
      ], ' · '),
      detailRoute: REPORTING_ROUTE,
      status: 'open',
    })
  }

  if (pendingCount > 0) {
    out.push({
      id: 'live-missing:pending-assignment',
      domain: 'reporting',
      occurredAt: `${targetDate}T23:59:58`,
      summary: `待归属填报 ${pendingCount} 条`,
      detail: joinNonEmpty([
        missingMachineCount > 0 ? `缺机列 ${missingMachineCount} 条` : '',
        missingShiftCount > 0 ? `缺班次 ${missingShiftCount} 条` : '',
      ], ' · '),
      detailRoute: REPORTING_ROUTE,
      status: 'open',
    })
  }

  safeArray(ownerStatus.items).forEach((row, idx) => {
    if (!statusIsMissing(row.status || row.submit_status || row.submitStatus)) return
    out.push({
      id: `live-missing-owner:${row.role_label || row.role || idx}:${row.person_name || row.username || idx}`,
      domain: 'reporting',
      occurredAt: row.updated_at || row.created_at || `${targetDate}T23:59:57`,
      summary: `未填报角色：${joinNonEmpty([
        row.role_label || row.role,
        row.person_name || row.username,
        row.workshop_name,
      ], ' · ')}`,
      detail: row.status_label || row.status || '待提交',
      detailRoute: REPORTING_ROUTE,
      status: 'open',
    })
  })

  return out
}

function traceRoute(traceId, detailRoute) {
  if (typeof detailRoute === 'string' && detailRoute.trim()) return detailRoute
  return traceId
    ? `/manage/alerts?trace_id=${encodeURIComponent(traceId)}`
    : '/manage/alerts'
}

function dailyOccurredAt(row, targetDate, fallbackTime) {
  const eventDate = row.target_date || row.targetDate || targetDate
  const raw = row.occurred_at || row.occurredAt || row.created_at || row.createdAt
  const time = typeof raw === 'string' ? raw.match(/T(\d{2}:\d{2}:\d{2}(?:\.\d+)?)/)?.[1] : null
  return `${eventDate}T${time || fallbackTime}`
}

function dailyFactEvent(kind, row, idx, targetDate, fallbackTime) {
  const eventDate = row.target_date || row.targetDate || targetDate
  const traceId = typeof (row.trace_id ?? row.traceId) === 'string'
    ? String(row.trace_id ?? row.traceId).trim()
    : ''
  const field = row.field || row.field_name || '关键事实'
  const rawId = row.id ?? row.trace_id ?? row.traceId ?? row.field ?? row.field_name ?? idx
  const labels = {
    'fact-conflict': `${field} 事实冲突`,
    'fact-missing': `${field} 缺少可信事实`,
    'hermes-failure': `${row.agent_code || row.agentCode || 'Hermes'} 运行失败`,
    'dingtalk-failure': `${row.agent_code || row.agentCode || '钉钉入站'} 运行失败`,
  }
  const factSource = safeFactSource(row.source ?? row.source_type, field)
  const sourceLabel = kind.startsWith('fact-')
    ? (factSource || '暂无可信来源')
    : factSource
  const workflowStatus = row.task_status || row.taskStatus || row.status
  const factStatus = row.fact_status || row.factStatus || row.status || null
  const groupKey = kind.startsWith('fact-')
    ? actionGroupKey('daily-fact', [kind, row.field || row.field_name || rawId])
    : undefined
  return {
    id: `${kind}:${rawId}`,
    groupKey,
    domain: kind === 'fact-conflict'
      ? 'reconciliation'
      : (kind === 'hermes-failure' ? 'production' : 'reporting'),
    occurredAt: dailyOccurredAt(row, eventDate, fallbackTime),
    targetDate: eventDate,
    summary: row.summary || labels[kind],
    detail: joinNonEmpty([row.field || row.field_name, sourceLabel, row.channel, factStatus], ' · '),
    detailRoute: traceRoute(traceId, row.detail_route || row.detailRoute),
    actionRoute: row.action_route || row.actionRoute || '',
    traceId,
    factStatus,
    status: workflowStatus === 'resolved' ? 'resolved' : 'open',
  }
}

export function normalizeDailyFactAlerts(payload, targetDate) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return []
  const groups = [
    ['fact-conflict', safeArray(payload.fact_conflicts), '23:59:59'],
    ['fact-missing', safeArray(payload.fact_missing), '23:59:58'],
    ['hermes-failure', safeArray(payload.hermes_failures), '23:59:57'],
    ['dingtalk-failure', safeArray(payload.dingtalk_inbound_failures), '23:59:56'],
  ]
  const events = groups.flatMap(([kind, rows, fallbackTime]) => (
    rows
      .filter((row) => row && typeof row === 'object' && !Array.isArray(row))
      .map((row, idx) => dailyFactEvent(kind, row, idx, targetDate, fallbackTime))
  ))
  const capabilityStatus = payload.fact_closure_capability?.status
  if (payload.fact_closure_available === false || capabilityStatus === 'missing') {
    events.push({
      id: 'fact-closure-capability:missing',
      domain: 'reporting',
      occurredAt: `${targetDate}T23:59:55`,
      targetDate,
      summary: '当日事实闭包不可用',
      detail: '可信日结快照缺失',
      detailRoute: '/manage/today?section=daily-report',
      traceId: '',
      status: null,
      isFallback: true,
    })
  }
  return events
}

export function mergeAndSort(eventsArrays) {
  const merged = eventsArrays.flat()
  return merged.sort((a, b) => {
    if (a.occurredAt !== b.occurredAt) return a.occurredAt < b.occurredAt ? 1 : -1
    if (a.domain !== b.domain) return a.domain < b.domain ? -1 : 1
    return String(a.id).localeCompare(String(b.id))
  })
}

export function groupAlertEvents(events = []) {
  const buckets = new Map()
  safeArray(events).forEach((event, index) => {
    if (!event || typeof event !== 'object') return
    const key = event.groupKey || `event:${event.id ?? 'anonymous'}:${index}`
    const rows = buckets.get(key) || []
    rows.push(event)
    buckets.set(key, rows)
  })

  const cases = [...buckets.entries()].map(([groupKey, sourceEvents]) => {
    const latest = [...sourceEvents].sort((a, b) => (
      String(a.occurredAt || '') < String(b.occurredAt || '') ? 1 : -1
    ))[0]
    const sourceEventIds = sourceEvents
      .map((event) => event.id)
      .filter((id) => id !== null && id !== undefined)
      .map(String)
    const traceIds = [...new Set(
      sourceEvents
        .map((event) => String(event.traceId || '').trim())
        .filter(Boolean)
    )]
    const rawCount = sourceEvents.length
    const rawOpenCount = sourceEvents.filter((event) => event.status === 'open').length
    const auditDetail = rawCount > 1
      ? joinNonEmpty([
          `${rawCount} 条原始记录`,
          traceIds.length > 0 ? `${traceIds.length} 个追踪编号` : '',
        ], ' · ')
      : ''
    return {
      ...latest,
      id: rawCount > 1 ? `case:${groupKey}` : latest.id,
      groupKey,
      detail: joinNonEmpty([latest.detail, auditDetail], ' · '),
      status: rawOpenCount > 0
        ? 'open'
        : (sourceEvents.every((event) => event.status === 'resolved') ? 'resolved' : latest.status),
      rawCount,
      rawOpenCount,
      sourceEventIds,
      traceIds,
      sourceEvents,
    }
  })

  return mergeAndSort([cases])
}

function queueKeyForEvent(event = {}) {
  const text = `${event.summary || ''} ${event.domain || ''}`
  if (event.domain === 'reporting') return 'reporting'
  if (event.domain === 'quality') return 'quality'
  if (event.domain === 'reconciliation') return 'reconciliation'
  if (event.domain === 'mes') return 'mes'
  if (/缺报|催报|补录|退回|上报/.test(text)) return 'reporting'
  if (/能耗|用电|电耗|电工|天然气/.test(text)) return 'energy'
  if (/MES|机列|待归属|未匹配|外部/.test(text)) return 'mes'
  return 'production'
}

const ALERT_WORK_QUEUE_DEFS = [
  { key: 'reporting', title: '缺报补录', tone: 'danger', route: FD_ROUTE },
  { key: 'energy', title: '能耗核对', tone: 'warning', route: FD_ROUTE },
  { key: 'mes', title: 'MES 匹配', tone: 'warning', route: FD_ROUTE },
  { key: 'quality', title: '质量异常', tone: 'primary', route: Q_ROUTE },
  { key: 'reconciliation', title: '差异核对', tone: 'primary', route: R_ROUTE },
  { key: 'production', title: '生产异常', tone: 'warning', route: FD_ROUTE },
]

export function buildAlertWorkQueues(events = []) {
  const cases = safeArray(events).every((event) => (
    Number.isInteger(event?.rawCount) && Array.isArray(event?.sourceEvents)
  ))
    ? safeArray(events)
    : groupAlertEvents(events)
  const buckets = Object.fromEntries(ALERT_WORK_QUEUE_DEFS.map((item) => [item.key, []]))
  cases.filter((event) => !event?.isFallback).forEach((event) => {
    const key = queueKeyForEvent(event)
    buckets[key].push(event)
  })

  return ALERT_WORK_QUEUE_DEFS.map((item) => {
    const rows = buckets[item.key] || []
    return {
      ...item,
      count: rows.length,
      rawCount: rows.reduce((sum, event) => sum + Number(event.rawCount || 1), 0),
      openCount: rows.filter((event) => event.status === 'open').length,
      openRawCount: rows.reduce(
        (sum, event) => sum + Number(event.rawOpenCount ?? (event.status === 'open' ? event.rawCount || 1 : 0)),
        0
      ),
      items: rows.slice(0, 3).map((event) => ({
        id: event.id,
        text: event.summary || '待处理异常',
        detail: event.detail || '',
        route: event.detailRoute || item.route,
        status: event.status || 'open',
        rawCount: Number(event.rawCount || 1),
        traceCount: safeArray(event.traceIds).length,
      })),
    }
  })
}
