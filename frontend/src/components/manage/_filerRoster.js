// Authoritative machine inventory per workshop, sourced from 5/24 现场表
// "铸轧铸锭（一） 26-5-24.xlsx" + "其余分厂（二） 26-5-24.xlsx".
// online=true means 当日 ✔ on 状态/开机 columns.
// Match workshops by name (workshops table.name).
const WORKSHOP_MACHINES = {
  铸锭车间: [
    { id: '1#', online: true },
    { id: '2#', online: true },
    { id: '3#', online: true },
    { id: '4#', online: true }
  ],
  铸二车间: [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: false }, { id: '6#', online: true }
  ],
  铸三车间: [
    { id: '1#', online: false }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: true }, { id: '6#', online: true },
    { id: '7#', online: true }, { id: '8#', online: true }, { id: '9#', online: true }
  ],
  铸五车间: [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: true },
    { id: '6#', online: true }, { id: '7#', online: true }
  ],
  铸六车间: [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: false },
    { id: '4#', online: true }, { id: '5#', online: false }, { id: '6#', online: true },
    { id: '7#', online: true }, { id: '8#', online: true }, { id: '9#', online: true },
    { id: '10#', online: false }
  ],
  热轧车间: [
    { id: '锯床', online: true },
    { id: '六面铣', online: true },
    { id: '双面铣', online: true },
    { id: '中厚板', online: true },
    { id: '加热炉', online: true },
    { id: '热轧机', online: true }
  ],
  '2050冷轧车间': [
    { id: '2050#', online: true }
  ],
  '1850冷轧车间': [
    { id: '1#', online: true }, { id: '2#', online: true }, { id: '3#', online: true },
    { id: '4#', online: true }, { id: '5#', online: true }
  ],
  '1650冷轧车间': [
    { id: '1650#', online: true }
  ],
  '1450冷轧车间': [
    { id: '1450#1', online: true }, { id: '1450#2', online: true },
    { id: '800#', online: true }, { id: '退火炉', online: true },
    { id: '剪切机', online: true }, { id: '拉矫机', online: true },
    { id: '重卷机', online: true }
  ],
  冷轧三车间: [
    { id: '1#', online: true }, { id: '2#', online: true },
    { id: '3#', online: true }, { id: '4#', online: true },
    { id: '重卷', online: true }
  ],
  精整车间: [
    { id: '19辊', online: true },
    { id: '新19辊', online: true },
    { id: '纵剪', online: true }
  ],
  二分厂精整车间: [
    { id: '19辊', online: true },
    { id: '新19辊', online: true },
    { id: '纵剪', online: true }
  ],
  园区剪切车间: [
    { id: '拉矫', online: true },
    { id: '大分切', online: true },
    { id: '小剪子', online: true },
    { id: '退火炉12个', online: true }
  ],
  在线退火: [
    { id: '新厂南', online: true },
    { id: '新厂北', online: true },
    { id: '园区南', online: true },
    { id: '园区北', online: true }
  ],
  在线退火车间: [
    { id: '新厂南', online: true },
    { id: '新厂北', online: true },
    { id: '园区南', online: true },
    { id: '园区北', online: true }
  ],
  彩涂车间: [
    { id: '涂漆生产线', online: true }
  ],
  回收车间: [
    { id: '2吨炉#1', online: true },
    { id: '12吨炉', online: false },
    { id: '2吨炉#2', online: true },
    { id: '磨机', online: true }
  ],
  花纹板车间: [
    { id: '花纹板生产线', online: true }
  ],
  成品库: [
    { id: '成品库', online: true }
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
  return WORKSHOP_MACHINES[workshopName] || []
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
  return reportingStatus.map((row) => {
    const operators = pickOperators(users, row.workshop_id)
    const machines = getMachinesFor(row.workshop_name)
    return {
      workshopId: row.workshop_id,
      workshopName: row.workshop_name || '',
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
