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
  if (dataSource === 'mixed') return 'MES + 填报'
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

export function buildLiveRealityStatus(aggregation = {}) {
  const progress = aggregation.overall_progress || aggregation.overallProgress || {}
  const context = aggregation.business_date_context || aggregation.businessDateContext || {}
  const binding = aggregation.mes_machine_binding || aggregation.mesMachineBinding || {}
  const requestedDate = context.requested_business_date || context.requestedBusinessDate || aggregation.business_date || '--'
  const currentDate = context.current_business_date || context.currentBusinessDate || requestedDate
  const activeDate = context.active_business_date || context.activeBusinessDate || requestedDate
  const currentDateEntryCount = numberValue(context.current_date_entry_count ?? context.currentDateEntryCount)
  const activeDateEntryCount = numberValue(context.active_date_entry_count ?? context.activeDateEntryCount)
  const fillEntryCount = numberValue(binding.fill_entry_count ?? binding.fillEntryCount ?? progress.total_entry_count ?? progress.totalEntryCount)
  const mesRowCount = numberValue(binding.mes_row_count ?? binding.mesRowCount)
  const matchedFillCount = numberValue(binding.fill_entries_with_mes_match ?? binding.fillEntriesWithMesMatch)
  const boundFillCount = numberValue(binding.fill_entries_bound_to_machine ?? binding.fillEntriesBoundToMachine)
  const pendingMachineCount = numberValue(binding.fill_entries_pending_machine ?? binding.fillEntriesPendingMachine ?? binding.pending_machine_assignment_count)
  const routeInferredCount = numberValue(binding.route_inferred_machine_count ?? binding.routeInferredMachineCount)
  const missingMachineCodeCount = numberValue(binding.upstream_machine_code_missing_count ?? binding.upstreamMachineCodeMissingCount)
  const isCurrentDateEmpty = currentDateEntryCount === 0 && currentDate !== activeDate

  return {
    tone: isCurrentDateEmpty ? 'warning' : 'success',
    primaryLabel: `当前显示 ${requestedDate}`,
    currentDateLabel: currentDateEntryCount > 0
      ? `今天 ${currentDate} 已填报 ${currentDateEntryCount} 卷`
      : `今天 ${currentDate} 暂无填报`,
    activeDateLabel: activeDate && activeDate !== currentDate
      ? `最近有效日 ${activeDate} · ${activeDateEntryCount} 卷`
      : `有效填报 ${activeDateEntryCount} 卷`,
    fillLabel: `填报端 ${fillEntryCount} 卷`,
    mesLabel: `外部 MES ${mesRowCount} 行`,
    matchLabel: `匹配填报 ${matchedFillCount} 卷`,
    bindingLabel: `已绑机列 ${boundFillCount} 卷`,
    routeLabel: `路线推断 ${routeInferredCount} 行`,
    upstreamLabel: missingMachineCodeCount > 0 ? `上游机列码缺失 ${missingMachineCodeCount} 行` : '上游机列码完整',
    pendingLabel: `待归属 ${pendingMachineCount} 卷`,
  }
}

export function shouldSwitchToRealtimeBusinessDate({
  targetDate,
  eventBusinessDate,
  aggregation = {},
  autoMode = true,
} = {}) {
  const eventDate = String(eventBusinessDate || '').trim()
  const currentTarget = String(targetDate || '').trim()
  if (!autoMode || !eventDate || !currentTarget || eventDate === currentTarget) return false

  const context = aggregation.business_date_context || aggregation.businessDateContext || {}
  const requestedDate = String(context.requested_business_date || context.requestedBusinessDate || aggregation.business_date || currentTarget)
  const currentDate = String(context.current_business_date || context.currentBusinessDate || requestedDate)
  const activeDate = String(context.active_business_date || context.activeBusinessDate || requestedDate)
  const requestedEntryCount = numberValue(context.requested_entry_count ?? context.requestedEntryCount)
  const currentDateEntryCount = numberValue(context.current_date_entry_count ?? context.currentDateEntryCount)

  const targetIsCurrentDate = currentTarget === currentDate && requestedDate === currentTarget
  if (targetIsCurrentDate && requestedEntryCount === 0 && currentDateEntryCount === 0) {
    return true
  }

  return currentTarget === activeDate && eventDate === currentDate
}

export function shouldRedirectToActiveBusinessDate({
  targetDate,
  aggregation = {},
  autoMode = true,
} = {}) {
  const currentTarget = String(targetDate || '').trim()
  if (!autoMode || !currentTarget) return ''

  const context = aggregation.business_date_context || aggregation.businessDateContext || {}
  const requestedDate = String(context.requested_business_date || context.requestedBusinessDate || aggregation.business_date || currentTarget)
  const currentDate = String(context.current_business_date || context.currentBusinessDate || requestedDate)
  const activeDate = String(context.active_business_date || context.activeBusinessDate || '').trim()
  if (!activeDate || activeDate === currentTarget) return ''

  const requestedEntryCount = numberValue(context.requested_entry_count ?? context.requestedEntryCount)
  const currentDateEntryCount = numberValue(context.current_date_entry_count ?? context.currentDateEntryCount)
  const activeDateEntryCount = numberValue(context.active_date_entry_count ?? context.activeDateEntryCount)
  const targetIsCurrentDate = currentTarget === currentDate && requestedDate === currentTarget
  if (targetIsCurrentDate && requestedEntryCount === 0 && currentDateEntryCount === 0 && activeDateEntryCount > 0) {
    return activeDate
  }
  return ''
}

export function buildPendingAssignmentSummary(aggregation = {}, limit = 3) {
  const progress = aggregation.overall_progress || aggregation.overallProgress || {}
  const rawSummary = progress.pending_assignment || progress.pendingAssignment || aggregation.pending_assignment || {}
  const rows = Array.isArray(rawSummary.rows) ? rawSummary.rows : []
  const safeLimit = Math.max(Number(limit) || 0, 0)

  return {
    entryCount: numberValue(rawSummary.entry_count ?? rawSummary.entryCount),
    draftEntryCount: numberValue(rawSummary.draft_entry_count ?? rawSummary.draftEntryCount),
    formalEntryCount: numberValue(rawSummary.formal_entry_count ?? rawSummary.formalEntryCount),
    missingMachineCount: numberValue(rawSummary.missing_machine_count ?? rawSummary.missingMachineCount),
    missingShiftCount: numberValue(rawSummary.missing_shift_count ?? rawSummary.missingShiftCount),
    workshopCount: numberValue(rawSummary.workshop_count ?? rawSummary.workshopCount),
    shiftCount: numberValue(rawSummary.shift_count ?? rawSummary.shiftCount),
    input: numberValue(rawSummary.input),
    output: numberValue(rawSummary.output),
    rows: rows.slice(0, safeLimit).map((row) => ({
      workshopName: row.workshop_name || row.workshopName || '--',
      shiftName: row.shift_name || row.shiftName || '未标记班次',
      entryCount: numberValue(row.entry_count ?? row.entryCount),
      draftEntryCount: numberValue(row.draft_entry_count ?? row.draftEntryCount),
      formalEntryCount: numberValue(row.formal_entry_count ?? row.formalEntryCount),
      missingMachineCount: numberValue(row.missing_machine_count ?? row.missingMachineCount),
      missingShiftCount: numberValue(row.missing_shift_count ?? row.missingShiftCount),
      input: numberValue(row.input),
      output: numberValue(row.output),
    })),
    tone: numberValue(rawSummary.entry_count ?? rawSummary.entryCount) > 0 ? 'warning' : 'success',
  }
}

export function buildMissingOutputWeightSummary(aggregation = {}, limit = 3) {
  const quality = aggregation.data_quality || aggregation.dataQuality || {}
  const rawSummary = quality.missing_output_weight || quality.missingOutputWeight || {}
  const items = Array.isArray(rawSummary.items) ? rawSummary.items : []
  const safeLimit = Math.max(Number(limit) || 0, 0)
  const entryCount = numberValue(rawSummary.entry_count ?? rawSummary.entryCount)

  return {
    entryCount,
    input: numberValue(rawSummary.input),
    scrap: numberValue(rawSummary.scrap),
    items: items.slice(0, safeLimit).map((item) => ({
      entryId: item.entry_id ?? item.entryId ?? null,
      workOrderId: item.work_order_id ?? item.workOrderId ?? null,
      trackingCardNo: item.tracking_card_no || item.trackingCardNo || '--',
      workshopName: item.workshop_name || item.workshopName || '未标记车间',
      machineName: item.machine_name || item.machineName || '未标记机列',
      shiftName: item.shift_name || item.shiftName || '未标记班次',
      inputWeight: numberValue(item.input_weight ?? item.inputWeight),
      scrapWeight: numberValue(item.scrap_weight ?? item.scrapWeight),
      entryStatus: item.entry_status || item.entryStatus || '',
    })),
    tone: entryCount > 0 ? 'danger' : 'success',
  }
}

export function buildWorkshopFillIntakeRows(workshops = [], limit = 6) {
  const rows = (workshops || []).map((workshop) => {
    const total = workshop.workshop_total || workshop.workshopTotal || {}
    const formalEntryCount = numberValue(total.formal_entry_count ?? total.formalEntryCount)
    const draftEntryCount = numberValue(total.draft_entry_count ?? total.draftEntryCount)
    const totalEntryCount = numberValue(total.total_entry_count ?? total.totalEntryCount ?? formalEntryCount + draftEntryCount)
    const cells = flattenCells([workshop]).filter((cell) => cell.is_applicable !== false)
    const missingCellCount = numberValue(total.missing_cell_count ?? cells.filter((cell) => cell.submission_status === 'not_started').length)
    const meterTotal = totalEntryCount + missingCellCount

    return {
      workshopName: workshop.workshop_name || workshop.workshopName || '--',
      formalEntryCount,
      draftEntryCount,
      totalEntryCount,
      missingCellCount,
      formalRate: meterTotal > 0 ? Number(((formalEntryCount / meterTotal) * 100).toFixed(2)) : 0,
      draftRate: meterTotal > 0 ? Number(((draftEntryCount / meterTotal) * 100).toFixed(2)) : 0,
      missingRate: meterTotal > 0 ? Number(((missingCellCount / meterTotal) * 100).toFixed(2)) : 0,
      tone: draftEntryCount > 0 ? 'warning' : (missingCellCount > 0 ? 'danger' : 'success'),
    }
  })
    .filter((row) => row.totalEntryCount + row.missingCellCount > 0)
    .sort((left, right) => (
      right.draftEntryCount - left.draftEntryCount ||
      right.missingCellCount - left.missingCellCount ||
      right.totalEntryCount - left.totalEntryCount ||
      left.workshopName.localeCompare(right.workshopName, 'zh-Hans-CN')
    ))

  return rows.slice(0, Math.max(Number(limit) || 0, 0))
}
