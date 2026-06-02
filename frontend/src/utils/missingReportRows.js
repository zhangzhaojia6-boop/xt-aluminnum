function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function isMissingCell(cell = {}) {
  return cell.is_applicable !== false
    && (cell.submission_status === 'not_started' || cell.status_text === '缺报')
}

export function buildMissingReportRows(payload = {}) {
  const machineRows = safeArray(payload.workshops).flatMap((workshop) =>
    safeArray(workshop.machines).flatMap((machine) =>
      safeArray(machine.shifts)
        .filter(isMissingCell)
        .map((shift) => ({
          key: `machine-${workshop.workshop_id}-${machine.machine_id}-${shift.shift_id}`,
          workshopName: workshop.workshop_name || '-',
          machineName: machine.machine_name || '-',
          shiftName: shift.shift_name || '-',
          roleLabel: '主操',
          ownerName: '-',
          statusText: shift.status_text || '缺报',
        }))
    )
  )

  const ownerRows = safeArray(payload.owner_daily_status?.items)
    .filter((item) => item.status !== 'submitted')
    .map((item) => ({
      key: `owner-${item.user_id || item.username}`,
      workshopName: item.workshop_name || '全厂专项',
      machineName: '每日一录',
      shiftName: '每日一录',
      roleLabel: item.role_label || item.role || '内勤岗',
      ownerName: item.person_name || item.username || '-',
      statusText: item.status === 'late' ? '迟报' : '缺报',
    }))

  return [...machineRows, ...ownerRows]
}

export function summarizeMissingReportRows(rows = []) {
  const workshops = new Set()
  const shifts = new Set()
  const roles = new Set()
  for (const row of rows) {
    if (row.workshopName && row.workshopName !== '-') workshops.add(row.workshopName)
    if (row.shiftName && row.shiftName !== '-') shifts.add(row.shiftName)
    if (row.roleLabel && row.roleLabel !== '-') roles.add(row.roleLabel)
  }
  return {
    total: rows.length,
    workshopCount: workshops.size,
    shiftCount: shifts.size,
    roleCount: roles.size,
  }
}
