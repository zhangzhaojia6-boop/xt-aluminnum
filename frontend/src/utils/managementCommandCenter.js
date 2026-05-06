function numberValue(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function flattenCells(workshops = []) {
  return workshops.flatMap((workshop) =>
    (workshop.machines || []).flatMap((machine) => machine.shifts || [])
  )
}

export function statusToneForCell(cell = {}) {
  if (cell.status_tone) return cell.status_tone
  if (!cell.is_applicable || cell.submission_status === 'not_applicable') return 'muted'
  if (numberValue(cell.attendance_exception_count) > 0) return 'danger'
  if (cell.submission_status === 'not_started') return 'danger'
  if (cell.submission_status === 'in_progress') return 'warning'
  if (['pending', 'not_started'].includes(cell.attendance_status)) return 'warning'
  if (cell.submission_status === 'all_submitted') return 'success'
  return 'muted'
}

export function statusTextForCell(cell = {}) {
  if (cell.status_text) return cell.status_text
  if (!cell.is_applicable || cell.submission_status === 'not_applicable') return '不适用'
  if (numberValue(cell.attendance_exception_count) > 0) return '考勤异常'
  if (cell.submission_status === 'not_started') return '缺报'
  if (cell.submission_status === 'in_progress') return '进行中'
  if (['pending', 'not_started'].includes(cell.attendance_status)) return '考勤待确认'
  if (cell.submission_status === 'all_submitted') return '已填'
  return '未开始'
}

export function isAttentionCell(cell = {}) {
  return ['danger', 'warning'].includes(statusToneForCell(cell))
}

export function workshopAttentionCount(workshop = {}) {
  return flattenCells([workshop]).filter((cell) => cell.is_applicable !== false && isAttentionCell(cell)).length
}

export function sortWorkshopsForCommandCenter(workshops = []) {
  return [...workshops].sort((left, right) => {
    const attentionDiff = workshopAttentionCount(right) - workshopAttentionCount(left)
    if (attentionDiff !== 0) return attentionDiff
    return numberValue(left.sort_order ?? left.workshop_id) - numberValue(right.sort_order ?? right.workshop_id)
  })
}

export function dataSourceLabel(dataSource) {
  if (dataSource === 'mes_projection') return 'MES 投影'
  if (dataSource === 'local_shift_data') return '卷级直录'
  if (dataSource === 'work_order_compat' || dataSource === 'work_order_runtime') return '工单兼容口径'
  return '未知来源'
}

export function buildOutputDistribution(workshops = [], limit = 5) {
  const rows = workshops.flatMap((workshop) =>
    (workshop.machines || []).map((machine) => {
      const output = numberValue(machine.day_total?.output)
      const input = numberValue(machine.day_total?.input)
      const shifts = (machine.shifts || [])
        .filter((shift) => numberValue(shift.total_output) > 0)
        .map((shift) => String(shift.shift_name || '').trim())
        .filter(Boolean)

      return {
        workshopName: workshop.workshop_name || '--',
        machineName: machine.machine_name || '--',
        machineId: machine.machine_id,
        bindingLabel: Number(machine.machine_id) < 0 ? '未绑定' : '已绑定',
        shiftLabel: shifts.length ? shifts.join(' / ') : '全班次',
        output,
        input,
      }
    })
  )
    .filter((row) => row.output > 0)
    .sort((left, right) => right.output - left.output)

  const maxOutput = rows[0]?.output || 0
  return rows.slice(0, Math.max(Number(limit) || 0, 0)).map((row) => ({
    ...row,
    share: maxOutput > 0 ? Number(((row.output / maxOutput) * 100).toFixed(2)) : 0,
  }))
}

function isUnboundMachine(machine = {}) {
  const bindingStatus = String(machine.machine_binding_status || machine.machineBindingStatus || '').toLowerCase()
  return bindingStatus === 'unbound' || Number(machine.machine_id ?? machine.machineId) < 0
}

export function buildUnboundFillSummary(workshops = [], limit = 3) {
  const rows = []

  workshops.forEach((workshop) => {
    const workshopName = workshop.workshop_name || workshop.workshopName || '--'
    const machines = workshop.machines || []
    machines.forEach((machine) => {
      if (!isUnboundMachine(machine)) return
      const output = numberValue(machine.day_total?.output ?? machine.dayTotal?.output)
      if (output <= 0) return
      const input = numberValue(machine.day_total?.input ?? machine.dayTotal?.input)
      const shiftNames = (machine.shifts || [])
        .filter((shift) => numberValue(shift.total_output ?? shift.totalOutput) > 0)
        .map((shift) => String(shift.shift_name || shift.shiftName || '').trim())
        .filter(Boolean)

      rows.push({
        workshopName,
        machineName: machine.machine_name || machine.machineName || '未绑定机列',
        shiftNames,
        shiftLabel: shiftNames.length ? shiftNames.join(' / ') : '全班次',
        output: Number(output.toFixed(2)),
        input: Number(input.toFixed(2)),
      })
    })
  })

  rows.sort((left, right) => right.output - left.output)
  const workshopNames = new Set(rows.map((row) => row.workshopName))
  const shiftNames = new Set(rows.flatMap((row) => row.shiftNames.length ? row.shiftNames : [row.shiftLabel]))
  const safeLimit = Math.max(Number(limit) || 0, 0)

  return {
    rowCount: rows.length,
    workshopCount: workshopNames.size,
    shiftCount: shiftNames.size,
    output: Number(rows.reduce((sum, row) => sum + row.output, 0).toFixed(2)),
    input: Number(rows.reduce((sum, row) => sum + row.input, 0).toFixed(2)),
    rows: rows.slice(0, safeLimit),
  }
}

export function buildMachineOwnershipSummary(workshops = []) {
  const summary = {
    totalOutput: 0,
    boundOutput: 0,
    unboundOutput: 0,
    boundMachineCount: 0,
    unboundMachineCount: 0,
  }

  workshops.forEach((workshop) => {
    const machines = workshop.machines || []
    machines.forEach((machine) => {
      const output = numberValue(machine.day_total?.output ?? machine.dayTotal?.output)
      if (output <= 0) return

      summary.totalOutput += output
      if (isUnboundMachine(machine)) {
        summary.unboundOutput += output
        summary.unboundMachineCount += 1
      } else {
        summary.boundOutput += output
        summary.boundMachineCount += 1
      }
    })
  })

  const totalOutput = Number(summary.totalOutput.toFixed(2))
  const boundOutput = Number(summary.boundOutput.toFixed(2))
  const unboundOutput = Number(summary.unboundOutput.toFixed(2))
  const machineCount = summary.boundMachineCount + summary.unboundMachineCount

  return {
    totalOutput,
    boundOutput,
    unboundOutput,
    boundMachineCount: summary.boundMachineCount,
    unboundMachineCount: summary.unboundMachineCount,
    machineCount,
    ownershipRate: totalOutput > 0 ? Number(((boundOutput / totalOutput) * 100).toFixed(2)) : 0,
    unboundRate: totalOutput > 0 ? Number(((unboundOutput / totalOutput) * 100).toFixed(2)) : 0,
    needsBinding: unboundOutput > 0,
  }
}

export function buildShiftOutputRhythm(workshops = []) {
  const shiftsByName = new Map()

  workshops.forEach((workshop) => {
    const machines = workshop.machines || []
    machines.forEach((machine) => {
      const shifts = machine.shifts || []
      shifts.forEach((shift) => {
        const output = numberValue(shift.total_output)
        if (output <= 0) return
        const shiftName = String(shift.shift_name || '').trim() || '未命名班次'
        if (!shiftsByName.has(shiftName)) {
          shiftsByName.set(shiftName, {
            shiftName,
            output: 0,
            input: 0,
            machineKeys: new Set(),
            workshopKeys: new Set(),
          })
        }

        const row = shiftsByName.get(shiftName)
        row.output += output
        row.input += numberValue(shift.total_input)
        row.machineKeys.add(
          `${workshop.workshop_id ?? workshop.workshop_name}-${machine.machine_id ?? machine.machine_name}`,
        )
        row.workshopKeys.add(`${workshop.workshop_id ?? workshop.workshop_name}`)
      })
    })
  })

  const rows = [...shiftsByName.values()].sort((left, right) => right.output - left.output)
  const totalOutput = rows.reduce((sum, row) => sum + row.output, 0)
  return rows.map((row) => ({
    shiftName: row.shiftName,
    output: Number(row.output.toFixed(2)),
    input: Number(row.input.toFixed(2)),
    machineCount: row.machineKeys.size,
    workshopCount: row.workshopKeys.size,
    share: totalOutput > 0 ? Number(((row.output / totalOutput) * 100).toFixed(2)) : 0,
  }))
}

export function formatSyncLag(seconds) {
  const lag = Number(seconds)
  if (!Number.isFinite(lag)) return '--'
  if (lag < 60) return `${lag.toFixed(0)}s`
  return `${(lag / 60).toFixed(1)}m`
}

export function buildCommandCenterSummary(aggregation = {}) {
  const progress = aggregation.overall_progress || {}
  const cells = flattenCells(aggregation.workshops || []).filter((cell) => cell.is_applicable !== false)
  const submittedCells = numberValue(progress.submitted_cells)
  const totalCells = numberValue(progress.total_cells)
  const fallbackMissing = cells.filter((cell) => cell.submission_status === 'not_started').length
  const fallbackAttention = cells.filter(isAttentionCell).length
  const completionRate = progress.completion_rate ?? (totalCells ? (submittedCells / totalCells) * 100 : 0)

  return {
    submittedCells,
    totalCells,
    missingCellCount: numberValue(progress.missing_cell_count ?? fallbackMissing),
    attentionCellCount: numberValue(progress.attention_cell_count ?? fallbackAttention),
    completionRate: Number(Number(completionRate).toFixed(2)),
    todayOutput: numberValue(aggregation.factory_total?.output),
    yieldRate: aggregation.factory_total?.yield_rate ?? null,
    dataSourceLabel: dataSourceLabel(aggregation.data_source),
    syncLagLabel: formatSyncLag(aggregation.mes_sync_status?.lag_seconds),
  }
}

export function buildFillIntakeSummary(aggregation = {}) {
  const progress = aggregation.overall_progress || {}
  const formalEntryCount = numberValue(progress.formal_entry_count)
  const draftEntryCount = numberValue(progress.draft_entry_count)
  const fallbackTotal = formalEntryCount + draftEntryCount
  const totalEntryCount = numberValue(progress.total_entry_count ?? fallbackTotal)
  const missingCellCount = numberValue(progress.missing_cell_count)
  const formalRate = totalEntryCount > 0 ? Number(((formalEntryCount / totalEntryCount) * 100).toFixed(2)) : 0
  const draftRate = totalEntryCount > 0 ? Number(((draftEntryCount / totalEntryCount) * 100).toFixed(2)) : 0

  return {
    formalEntryCount,
    draftEntryCount,
    totalEntryCount,
    missingCellCount,
    formalRate,
    draftRate,
    tone: draftEntryCount > 0 ? 'warning' : (missingCellCount > 0 ? 'danger' : 'success'),
  }
}
