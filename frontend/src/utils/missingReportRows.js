import { compareShiftLabels, formatShiftLabel } from './display.js'

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
          shiftName: formatShiftLabel(shift.shift_name),
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

  machineRows.sort((left, right) => {
    const workshopDiff = left.workshopName.localeCompare(right.workshopName, 'zh-Hans-CN')
    if (workshopDiff !== 0) return workshopDiff
    const shiftDiff = compareShiftLabels(left.shiftName, right.shiftName)
    if (shiftDiff !== 0) return shiftDiff
    return left.machineName.localeCompare(right.machineName, 'zh-Hans-CN')
  })

  ownerRows.sort((left, right) => left.roleLabel.localeCompare(right.roleLabel, 'zh-Hans-CN'))
  return [...machineRows, ...ownerRows]
}

export function summarizeMissingReportRows(rows = []) {
  const workshops = new Set()
  const shifts = new Set()
  const roles = new Set()
  const roleBuckets = {
    operator: 0,
    electrician: 0,
    owner: 0,
  }
  for (const row of rows) {
    if (row.workshopName && row.workshopName !== '-') workshops.add(row.workshopName)
    if (row.shiftName && row.shiftName !== '-') shifts.add(row.shiftName)
    if (row.roleLabel && row.roleLabel !== '-') roles.add(row.roleLabel)
    const roleLabel = String(row.roleLabel || '')
    if (roleLabel.includes('电工') || roleLabel.includes('能源') || roleLabel.includes('能耗')) {
      roleBuckets.electrician += 1
    } else if (row.shiftName === '每日一录' || row.machineName === '每日一录' || roleLabel.includes('内勤')) {
      roleBuckets.owner += 1
    } else {
      roleBuckets.operator += 1
    }
  }
  return {
    total: rows.length,
    workshopCount: workshops.size,
    shiftCount: shifts.size,
    roleCount: roles.size,
    roleBuckets,
  }
}
