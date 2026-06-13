import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildAuditTickerItems,
  buildFillLedgerRows,
  buildIssueQueues,
  buildSourceChainCards,
  explainWorkshopDataEmptyState,
  filterFillLedgerRows,
  isEnergyLedgerRow,
  isMachineProductionLedgerRow,
  MISSING_AUDIT_VALUE,
} from '../src/utils/manageFillDetailsAudit.js'
import {
  buildMissingReportRows,
  summarizeMissingReportRows,
} from '../src/utils/missingReportRows.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

const dailyOverview = {
  plant_output: {
    daily_output: 81.25,
    finished_inbound_output: 73.6,
    monthly_output: 1200,
    energy_per_ton: 456.7,
  },
  workshop_output: [
    { workshop: '园区在线', daily_output: 40 },
    { workshop: '精整', daily_output: 50 },
    { workshop: '冷轧三车间', daily_output: 99 },
  ],
  contracts: {
    daily_new: 12.5,
    remaining: 88.2,
    unit: '吨',
  },
  energy: {
    total_electricity: 1200,
    owner_electricity: 1180,
    data_available: true,
  },
  yield_rates: {
    daily: 96.4,
    owner_daily: 95.1,
  },
}

test('audit ticker uses plant inbound output and ton contract values', () => {
  const items = buildAuditTickerItems({
    dailyOverview,
    liveAggregation: {
      mes_sync_status: { status: 'recovering', lag_seconds: 84 },
    },
  })

  assert.equal(items.find((item) => item.key === 'plant-output')?.label, 'MES包装产量')
  assert.equal(items.find((item) => item.key === 'plant-output')?.value, '81.25 吨')
  assert.equal(items.find((item) => item.key === 'finished-inbound')?.label, '内勤入库填报')
  assert.equal(items.find((item) => item.key === 'finished-inbound')?.value, '73.6 吨')
  assert.equal(items.find((item) => item.key === 'process-throughput')?.value, '90 吨')
  assert.equal(items.find((item) => item.key === 'contract-tonnage')?.value, '12.5 吨')
  assert.equal(items.find((item) => item.key === 'mes-sync')?.value, '同步恢复中')
})

test('audit ticker hides trailing zero decimals without losing non-zero decimals', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      plant_output: { daily_output: 81, finished_inbound_output: 73 },
      contracts: { daily_new: 12.5, unit: '吨' },
      workshop_output: [{ workshop: '园区在线', daily_output: 40 }],
    },
  })

  assert.equal(items.find((item) => item.key === 'plant-output')?.value, '81 吨')
  assert.equal(items.find((item) => item.key === 'finished-inbound')?.value, '73 吨')
  assert.equal(items.find((item) => item.key === 'process-throughput')?.value, '40 吨')
  assert.equal(items.find((item) => item.key === 'contract-tonnage')?.value, '12.5 吨')
})

test('audit ticker never renders fake zero when energy is unavailable', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      energy: {
        data_available: false,
        total_electricity: 0,
        owner_electricity: null,
      },
    },
  })

  assert.equal(items.find((item) => item.key === 'algorithm-energy')?.value, MISSING_AUDIT_VALUE)
  assert.equal(items.find((item) => item.key === 'owner-energy')?.value, MISSING_AUDIT_VALUE)
})

test('audit ticker accepts electricity aliases shared with live and energy pages', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      energy: {
        total_electricity: 17430,
        owner_total_electricity: 17020,
        data_available: true,
      },
    },
  })

  assert.equal(items.find((item) => item.key === 'algorithm-energy')?.value, '17,430 度')
  assert.equal(items.find((item) => item.key === 'owner-energy')?.value, '17,020 度')
})

test('audit ticker does not display comprehensive total_energy as electricity', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      energy: {
        total_energy: 17430,
        owner_total_electricity: 17020,
        data_available: true,
      },
    },
  })

  assert.equal(items.find((item) => item.key === 'algorithm-energy')?.value, MISSING_AUDIT_VALUE)
  assert.equal(items.find((item) => item.key === 'owner-energy')?.value, '17,020 度')
})

test('audit ticker treats algorithm_total_energy as available energy data', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      energy: {
        algorithm_total_energy: 17430,
        owner_total_electricity: 17020,
        data_available: true,
      },
    },
  })

  assert.equal(items.find((item) => item.key === 'algorithm-energy')?.value, '17,430 度')
  assert.equal(items.find((item) => item.key === 'owner-energy')?.value, '17,020 度')
})

test('source chain cards keep algorithm values primary and filled values secondary', () => {
  const cards = buildSourceChainCards(dailyOverview)

  assert.deepEqual(
    cards.map((item) => [item.key, item.primaryLabel, item.compareLabel]),
    [
      ['output', 'MES包装', '内勤入库填报'],
      ['process', '车间合计', '最终口径'],
      ['energy', '算法总用电', '电工填报'],
      ['yield', '算法成品率', '内勤填报'],
      ['contract', '当天接合同', '总余合同量'],
    ],
  )
  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, '1,200 度')
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '1,180 度')
})

test('source chain cards accept electricity aliases shared with live and energy pages', () => {
  const cards = buildSourceChainCards({
    ...dailyOverview,
    energy: {
      total_electricity: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, '17,430 度')
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '17,020 度')
})

test('source chain cards do not display comprehensive total_energy as electricity', () => {
  const cards = buildSourceChainCards({
    ...dailyOverview,
    energy: {
      total_energy: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, MISSING_AUDIT_VALUE)
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '17,020 度')
})

test('source chain cards treat algorithm_total_energy as available energy data', () => {
  const cards = buildSourceChainCards({
    ...dailyOverview,
    energy: {
      algorithm_total_energy: 17430,
      owner_total_electricity: 17020,
      data_available: true,
    },
  })

  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, '17,430 度')
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '17,020 度')
})

test('fill ledger rows expose person, post, submit time and content', () => {
  const rows = buildFillLedgerRows([
    {
      row_id: 'entry-1',
      source_type: 'owner_daily',
      source_label: '每日一录',
      workshop_name: '精整',
      machine_name: '内勤岗',
      responsible_name: '张三',
      responsible_username: 'zhangsan',
      submitted_at: '2026-05-30T08:12:00',
      status: 'submitted',
      metrics: [
        { key: 'total_electricity_kwh', label: '全厂用电', value: 1200, unit: 'kWh' },
        { key: 'contract_no', label: '合同号', value: 'HT-001', unit: '' },
      ],
    },
    {
      row_id: 'entry-2',
      source_type: 'work_order_entry',
      source_label: '机台填报',
      workshop_name: '园区在线',
      machine_name: '1#退火炉',
      shift_name: '大夜',
      responsible_name: '李四',
      tracking_card_no: 'TX-001',
      output_weight: 9.5,
      updated_at: '2026-05-30T23:20:00',
      status: 'approved',
    },
  ])

  assert.equal(rows[0].machineName, '内勤岗')
  assert.equal(rows[0].shiftName, '每日一录')
  assert.equal(rows[0].responsibleText, '张三')
  assert.equal(rows[0].submittedText, '05-30 08:12')
  assert.match(rows[0].contentText, /全厂用电 1200kWh/)
  assert.match(rows[0].contentText, /合同号 HT-001/)
  assert.match(rows[1].contentText, /产量 9.5 吨/)
})

test('fill ledger search matches responsible person, machine and tracking card', () => {
  const rows = buildFillLedgerRows([
    { row_id: 'a', source_type: 'owner_daily', workshop_name: '精整', responsible_name: '张三', machine_name: '内勤岗' },
    { row_id: 'b', source_type: 'work_order_entry', workshop_name: '园区在线', responsible_name: '李四', machine_name: '1#退火炉', tracking_card_no: 'TX-001' },
    { row_id: 'c', source_type: 'mes_projection', responsible_name: '外部 MES', machine_name: 'MES 机列' },
  ])

  assert.deepEqual(filterFillLedgerRows(rows, { keyword: '张三' }).map((row) => row.rowId), ['a'])
  assert.deepEqual(filterFillLedgerRows(rows, { keyword: 'TX-001' }).map((row) => row.rowId), ['b'])
  assert.deepEqual(filterFillLedgerRows(rows, { sourceType: 'owner_daily' }).map((row) => row.rowId), ['a'])
  assert.deepEqual(rows.map((row) => row.rowId), ['a', 'b'])
})

test('workshop dashboard separates machine production rows from electrician energy rows', () => {
  const rows = buildFillLedgerRows([
    { row_id: 'machine', source_type: 'work_order_entry', workshop_name: '热轧', machine_name: '1#机', output_weight: 9.5 },
    { row_id: 'electric', source_type: 'mobile_shift_report', workshop_name: '热轧', machine_name: '电工岗', energy_kwh: 1200 },
    { row_id: 'energy', source_type: 'machine_energy', workshop_name: '热轧', machine_name: '总电工', gas_m3: 300 },
  ])

  assert.deepEqual(rows.filter(isMachineProductionLedgerRow).map((row) => row.rowId), ['machine'])
  assert.deepEqual(rows.filter(isEnergyLedgerRow).map((row) => row.rowId), ['electric', 'energy'])
})

test('workshop empty states explain whether data is loading, unselected, sync failed or absent', () => {
  assert.equal(explainWorkshopDataEmptyState({ loading: true, kind: 'mes' }), '加载中...')
  assert.equal(explainWorkshopDataEmptyState({ hasWorkshop: false, kind: 'mes' }), '请选择车间后查看外部 MES 明细')
  assert.equal(
    explainWorkshopDataEmptyState({ hasWorkshop: true, kind: 'mes', syncStatus: { status: 'failed' } }),
    '外部 MES 同步异常，请先查看系统设置中的同步状态',
  )
  assert.equal(
    explainWorkshopDataEmptyState({ hasWorkshop: true, kind: 'wip', syncStatus: { status: 'fresh' } }),
    '当前车间暂无当日在制料快照',
  )
})

test('issue queues surface pending assignment, missing owner roles, energy gaps and MES gaps', () => {
  const queues = buildIssueQueues({
    dailyOverview: {
      energy: { data_available: false },
    },
    liveAggregation: {
      overall_progress: {
        pending_assignment: { entry_count: 2, missing_machine_count: 1 },
      },
      owner_daily_status: {
        items: [
          { status: 'not_started', role_label: '电工', person_name: '王五', workshop_name: '全厂专项' },
        ],
      },
      mes_machine_binding: {
        unresolved_machine_count: 3,
        upstream_machine_code_missing_count: 1,
      },
    },
  })

  assert.deepEqual(queues.map((item) => [item.key, item.count]), [
    ['pending-assignment', 2],
    ['missing-owner', 1],
    ['missing-energy', 1],
    ['mes-unmatched', 3],
  ])

  const mesQueue = queues.find((item) => item.key === 'mes-unmatched')
  assert.deepEqual(mesQueue.items, ['未解析 3 条', '上游缺机列码 1 条'])
})

test('issue queues keep pending assignment tone when backend uses fallback count field', () => {
  const queues = buildIssueQueues({
    liveAggregation: {
      overall_progress: {
        pending_assignment: { pending_assignment_entry_count: 2 },
      },
    },
  })

  const pending = queues.find((item) => item.key === 'pending-assignment')
  assert.equal(pending.count, 2)
  assert.equal(pending.tone, 'warning')
})

test('FillDetailsPage is wired to the three audit data sources', () => {
  const src = source('../src/views/manage/fill-details/FillDetailsPage.vue')
  const realtimeApi = source('../src/api/realtime.js')

  assert.match(src, /buildFillDetailsStitchSurface/)
  assert.match(src, /stitchSurface\.value\.filteredRows/)
  assert.match(src, /stitchSurface\.value\.sourceChain/)
  assert.match(src, /stitchSurface\.value\.issueQueues/)
  assert.match(src, /stitchSurface\.value\.bottomStatus/)
  assert.match(src, /fetchDailyProduction/)
  assert.match(src, /fetchLiveAggregation/)
  assert.match(src, /fetchLiveFillDetails/)
  assert.match(src, /const FILL_DETAILS_PAGE_LIMIT = 800/)
  assert.match(src, /limit:\s*FILL_DETAILS_PAGE_LIMIT/)
  assert.match(src, /fetchMesFillGaps/)
  assert.match(src, /exportMissingReportExcel/)
  assert.match(realtimeApi, /fetchMesFillGaps/)
  assert.match(realtimeApi, /\/aggregation\/live\/mes-fill-gaps/)
  assert.match(src, /data-testid="fill-details-missing-export"/)
  assert.match(src, /data-testid="fill-details-mes-gap-panel"/)
  assert.match(src, /暂无 MES 对照异常/)
  assert.match(src, /mesGapRows/)
  assert.match(src, /mesGapSequenceText/)
  assert.match(src, /mesGapSpecText/)
  assert.match(src, /mesGapMachineText/)
  assert.match(src, /mesGapBindingText/)
  assert.match(src, /mesGapOperatorText/)
  assert.match(src, /mesGapCauseText/)
  assert.match(src, /row\.customer_alias/)
  assert.match(src, /row\.alloy_grade/)
  assert.match(src, /row\.material_state/)
  assert.match(src, /process_sequence/)
  assert.match(src, /typeof sequence === 'string'/)
  assert.match(src, /gap_cause/)
  assert.match(src, /MES:.*归属:.*本地:/)
  assert.match(src, /匹配.*可信度/)
  assert.match(src, /mes_worker_name/)
  assert.match(src, /mes_last_seen_at/)
  assert.match(src, /操作.*同步/)
  assert.match(src, /downloadBlob\(data,\s*`缺报明细-\$\{targetDate\.value\}\.xlsx`/)
  assert.match(src, /fetchWorkshops/)
  assert.match(src, /data-testid="fill-details-workshop-filter"/)
  assert.match(src, /workshop_id:\s*selectedWorkshopId\.value/)
  assert.match(src, /data-testid="data-audit-ticker"/)
  assert.match(src, /data-testid="source-chain-panel"/)
  assert.match(src, /data-testid="issue-queue-panel"/)
  assert.match(src, /data-testid="stitch-bottom-status"/)
  assert.doesNotMatch(src, /外部 MES/)
  assert.doesNotMatch(src, /value:\s*'mes_projection'/)
})

test('management navigation keeps alerts available in compact mode', () => {
  const src = source('../src/config/manage-navigation.js')

  assert.match(src, /COMPACT_REVIEW_PATHS/)
  assert.match(src, /'\/manage\/alerts'/)
})

test('energy page uses the shared management date switcher', () => {
  const src = source('../src/views/energy/EnergyCenter.vue')

  assert.match(src, /DateSwitcher/)
  assert.match(src, /@step="handleBusinessDateStep"/)
  assert.match(src, /@pick="handleBusinessDatePick"/)
})

test('user management creation roles only expose active business roles', () => {
  const src = source('../src/views/master/UserManagement.vue')

  assert.match(src, /ACTIVE_ROLE_OPTIONS/)
  assert.doesNotMatch(src, /value:\s*'shift_leader'/)
  assert.doesNotMatch(src, /value:\s*'team_leader'/)
  assert.doesNotMatch(src, /value:\s*'mobile_user'/)
  assert.doesNotMatch(src, /value:\s*'utility_manager'/)
  assert.doesNotMatch(src, /value:\s*'inventory_keeper'/)
  assert.doesNotMatch(src, /value:\s*'contracts'/)
})

test('missing report rows are precise to machine shift and owner role', () => {
  const rows = buildMissingReportRows({
    workshops: [
      {
        workshop_id: 1,
        workshop_name: '铸轧三',
        machines: [
          {
            machine_id: 9,
            machine_name: '9#机',
            shifts: [
              { shift_id: 1, shift_name: '大夜', submission_status: 'not_started', status_text: '缺报', is_applicable: true },
              { shift_id: 2, shift_name: '长白班', submission_status: 'all_submitted', status_text: '已填', is_applicable: true },
            ],
          },
        ],
      },
    ],
    owner_daily_status: {
      items: [
        { user_id: 30, workshop_name: '成品库', role_label: '总电工', person_name: '王电工', status: 'not_started' },
      ],
    },
  })

  assert.deepEqual(rows.map((row) => [row.workshopName, row.machineName, row.shiftName, row.roleLabel, row.statusText]), [
    ['铸轧三', '9#机', '大夜班', '主操', '缺报'],
    ['成品库', '每日一录', '每日一录', '总电工', '缺报'],
  ])
  assert.deepEqual(summarizeMissingReportRows(rows), {
    total: 2,
    workshopCount: 2,
    shiftCount: 2,
    roleCount: 2,
    roleBuckets: {
      operator: 1,
      electrician: 1,
      owner: 0,
    },
  })
})

test('TodayPage and WorkshopDashboardPage mount precise missing report panels', () => {
  const todaySrc = source('../src/views/manage/today/TodayPage.vue')
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(todaySrc, /MissingReportPanel/)
  assert.match(todaySrc, /compact/)
  assert.match(todaySrc, /fetchLiveAggregation/)
  assert.match(todaySrc, /buildTodayStitchSurface/)
  assert.match(todaySrc, /missingRows\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.missingReportRows/)
  assert.match(dashboardSrc, /MissingReportPanel/)
  assert.match(dashboardSrc, /data-testid="workshop-dashboard-filter"/)
  assert.match(dashboardSrc, /fetchMesWorkshopProcessRecords\(scopedParams/)
  assert.match(dashboardSrc, /fetchMesMaterialRecords\(scopedParams/)
  assert.match(dashboardSrc, /fetchMesFillGaps\(scopedParams/)
  assert.match(dashboardSrc, /exportMissingReportExcel/)
  assert.match(dashboardSrc, /data-testid="workshop-dashboard-missing-export"/)
  assert.match(dashboardSrc, /data-testid="workshop-dashboard-mes-gap-panel"/)
  assert.match(dashboardSrc, /暂无 MES 对照异常/)
  assert.match(dashboardSrc, /mesGapRows/)
  assert.match(dashboardSrc, /downloadBlob\(data,\s*`缺报明细-\$\{safeFilenameText\(workshopTitle\.value\)\}-\$\{targetDate\.value\}\.xlsx`/)
  assert.match(dashboardSrc, /explainWorkshopDataEmptyState/)
  assert.match(dashboardSrc, /isMachineProductionLedgerRow/)
  assert.match(dashboardSrc, /isEnergyLedgerRow/)
  assert.doesNotMatch(
    dashboardSrc,
    /unresolved_machine_count\s*\|\|\s*0\)\s*\+\s*Number\(mes\.upstream_machine_code_missing_count/,
  )
})

test('MissingReportPanel has compact density for yesterday report surface', () => {
  const src = source('../src/components/manage/MissingReportPanel.vue')

  assert.match(src, /compact/)
  assert.match(src, /xt-missing-report--compact/)
  assert.match(src, /xt-missing-report__chips/)
  assert.match(src, /props\.rows\.slice\(0,\s*1\)/)
  assert.match(src, /compactOverflowCount/)
  assert.match(src, /xt-missing-report__more/)
  assert.match(src, /compactRoleStats/)
  assert.match(src, /grid-template-columns:\s*auto minmax\(0,\s*1fr\)/)
})

test('missing report rows use canonical shift order before owner daily rows', () => {
  const rows = buildMissingReportRows({
    workshops: [
      {
        workshop_id: 2,
        workshop_name: '冷轧',
        machines: [
          {
            machine_id: 8,
            machine_name: '8#机',
            shifts: [
              { shift_id: 3, shift_name: '大夜', submission_status: 'not_started', is_applicable: true },
              { shift_id: 1, shift_name: '白班', submission_status: 'not_started', is_applicable: true },
              { shift_id: 2, shift_name: '小夜', submission_status: 'not_started', is_applicable: true },
            ],
          },
        ],
      },
    ],
    owner_daily_status: {
      items: [{ user_id: 9, role_label: '生产内勤', person_name: '内勤', status: 'not_started' }],
    },
  })

  assert.deepEqual(rows.map((row) => row.shiftName), ['长白班', '小夜班', '大夜班', '每日一录'])
})

test('WorkshopDashboardPage avoids a duplicate API load after selecting the default workshop', () => {
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(dashboardSrc, /const suppressWorkshopSelectionWatch = ref\(false\)/)
  assert.match(dashboardSrc, /suppressWorkshopSelectionWatch\.value = true[\s\S]*selectedWorkshopId\.value = workshops\.value\[0\]\.id/)
  assert.match(dashboardSrc, /watch\(selectedWorkshopId, \(\) => \{[\s\S]*if \(suppressWorkshopSelectionWatch\.value\)/)
})

test('WorkshopDashboardPage shows machine fill submit time', () => {
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(dashboardSrc, /<th>填报时间<\/th>/)
  assert.match(dashboardSrc, /row\.submittedText/)
  assert.match(dashboardSrc, /colspan="7"/)
})

test('WorkshopDashboardPage protects compact director view from text overflow', () => {
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(dashboardSrc, /\.workshop-board\s*\{[\s\S]*max-width:\s*100%/)
  assert.match(dashboardSrc, /\.workshop-board h1\s*\{[\s\S]*overflow-wrap:\s*anywhere/)
  assert.match(dashboardSrc, /\.workshop-board__table\s*\{[\s\S]*-webkit-overflow-scrolling:\s*touch/)
  assert.match(dashboardSrc, /@media \(max-width:\s*760px\)[\s\S]*overflow-x:\s*hidden/)
  assert.match(dashboardSrc, /\.workshop-board__mini-row b,[\s\S]*max-width:\s*45%/)
})
