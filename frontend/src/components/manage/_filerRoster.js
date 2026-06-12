import { filterActiveWorkshopRows, normalizeWorkshopName } from '../../utils/activeWorkshops.js'

const WORKSHOP_MACHINES = {
  铸锭: [
    { id: '1#', online: true },
    { id: '2#', online: true },
    { id: '3#', online: true },
    { id: '4#', online: true }
  ],
  铸二: [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: false }, { id: '6#', online: true }
  ],
  铸三: [
    { id: '1#', online: false }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: true }, { id: '6#', online: true },
    { id: '7#', online: true }, { id: '8#', online: true }, { id: '9#', online: true }
  ],
  热轧: [
    { id: '锯床', online: true },
    { id: '六面铣', online: true },
    { id: '双面铣', online: true },
    { id: '中厚板', online: true },
    { id: '加热炉', online: true },
    { id: '热轧机', online: true }
  ],
  精整: [
    { id: '19辊', online: true },
    { id: '新19辊', online: true },
    { id: '纵剪', online: true }
  ],
  拉矫: [
    { id: '拉矫', online: true }
  ],
  园区剪切: [
    { id: '大分切', online: true },
    { id: '小剪子', online: true }
  ],
  新厂在线: [
    { id: '新厂南', online: true },
    { id: '新厂北', online: true }
  ],
  园区在线: [
    { id: '园区南', online: true },
    { id: '园区北', online: true }
  ],
  冷轧2050: [
    { id: '2050#', online: true }
  ],
  冷轧1850: [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: true }
  ],
  冷轧1650: [
    { id: '1650#', online: true }
  ]
}

const STATUS_TONE = {
  submitted: 'success',
  reported: 'success',
  reviewed: 'success',
  late: 'warning',
  draft: 'warning',
  returned: 'danger',
  unreported: 'danger',
  not_started: 'danger',
  not_applicable: 'muted'
}

const STATUS_LABEL = {
  submitted: '已报',
  reported: '已报',
  reviewed: '已确认',
  late: '迟报',
  draft: '草稿',
  returned: '退回',
  unreported: '未报',
  not_started: '未报',
  not_applicable: '不适用'
}

export function statusTone(s) { return STATUS_TONE[s] || 'muted' }
export function statusLabel(s) { return STATUS_LABEL[s] || s || '未报' }

export function getMachinesFor(workshopName) {
  return WORKSHOP_MACHINES[normalizeWorkshopName(workshopName)] || []
}

function pickOperators(users, workshopId) {
  if (!Array.isArray(users)) return []
  return users
    .filter((u) =>
      u && u.role === 'machine_operator' &&
      Number(u.workshop_id) === Number(workshopId) &&
      u.is_active !== false
    )
    .map((u) => ({
      id: u.id,
      name: u.name || u.username || '',
      machineName: u.bound_machine_name || ''
    }))
}

export function buildFilerRoster(reportingStatus = [], users = []) {
  if (!Array.isArray(reportingStatus)) return []
  return filterActiveWorkshopRows(reportingStatus).map((row) => {
    const workshopName = normalizeWorkshopName(row.workshop_name || row.workshopName)
    const operators = pickOperators(users, row.workshop_id)
    const machines = getMachinesFor(workshopName)
    return {
      workshopId: row.workshop_id,
      workshopName,
      sourceLabel: row.source_label || '',
      reportStatus: row.report_status || 'unreported',
      statusHint: row.status_hint || '',
      outputWeight: row.output_weight ?? null,
      operatorCount: operators.length,
      operators,
      machines,
      machineCount: machines.length,
      onlineCount: machines.filter((m) => m.online).length
    }
  })
}

export function rosterStats(roster = []) {
  const total = roster.length
  let reported = 0
  let unreported = 0
  let abnormal = 0
  for (const r of roster) {
    const tone = statusTone(r.reportStatus)
    if (tone === 'success') reported += 1
    else if (tone === 'danger') unreported += 1
    else if (tone === 'warning') abnormal += 1
  }
  return { total, reported, unreported, abnormal }
}
