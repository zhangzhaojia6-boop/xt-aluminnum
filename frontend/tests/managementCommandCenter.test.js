import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { manageNavGroups } from '../src/config/manage-navigation.js'
import {
  buildCommandCenterSummary,
  buildFillIntakeSummary,
  buildLiveRealityStatus,
  buildMachineOwnershipSummary,
  buildMissingOutputWeightSummary,
  buildOutputDistribution,
  buildPendingAssignmentSummary,
  buildShiftOutputRhythm,
  buildUnboundFillSummary,
  buildWorkshopFillIntakeRows,
  dataSourceLabel,
  shouldRedirectToActiveBusinessDate,
  shouldSwitchToRealtimeBusinessDate,
  sortWorkshopsForCommandCenter,
  statusTextForCell,
  statusToneForCell,
} from '../src/utils/managementCommandCenter.js'

const liveDashboardSource = readFileSync(
  new URL('../src/views/reports/LiveDashboard.vue', import.meta.url),
  'utf8',
)
const costCenterSource = readFileSync(
  new URL('../src/views/review/CostAccountingCenter.vue', import.meta.url),
  'utf8',
)
const referenceFrameSource = readFileSync(
  new URL('../src/components/reference/ReferencePageFrame.vue', import.meta.url),
  'utf8',
)
const referenceCardSource = readFileSync(
  new URL('../src/components/reference/ReferenceModuleCard.vue', import.meta.url),
  'utf8',
)
const moduleTileSource = readFileSync(
  new URL('../src/components/xt/XtModuleTile.vue', import.meta.url),
  'utf8',
)
const routerSource = readFileSync(
  new URL('../src/router/index.js', import.meta.url),
  'utf8',
)
const realtimeApiSource = readFileSync(
  new URL('../src/api/realtime.js', import.meta.url),
  'utf8',
)
const executiveApiSource = readFileSync(
  new URL('../src/api/executive.js', import.meta.url),
  'utf8',
)

const baseAggregation = {
  overall_progress: {
    submitted_cells: 4,
    total_cells: 8,
    missing_cell_count: 2,
    attention_cell_count: 3,
    completion_rate: 50,
    formal_entry_count: 9,
    draft_entry_count: 3,
    total_entry_count: 12,
  },
  data_source: 'mes_projection',
  factory_total: {
    output: 126.4,
    yield_rate: 97.32,
  },
  mes_sync_status: {
    lag_seconds: 42,
  },
}

test('buildCommandCenterSummary exposes first-screen factory status', () => {
  const summary = buildCommandCenterSummary(baseAggregation)

  assert.equal(summary.submittedCells, 4)
  assert.equal(summary.totalCells, 8)
  assert.equal(summary.missingCellCount, 2)
  assert.equal(summary.attentionCellCount, 3)
  assert.equal(summary.completionRate, 50)
  assert.equal(summary.todayOutput, 126.4)
  assert.equal(summary.yieldRate, 97.32)
  assert.equal(summary.dataSourceLabel, 'MES 投影')
  assert.equal(summary.syncLagLabel, '42s')
})

test('buildFillIntakeSummary separates formal and draft entry intake', () => {
  const summary = buildFillIntakeSummary(baseAggregation)

  assert.equal(summary.formalEntryCount, 9)
  assert.equal(summary.draftEntryCount, 3)
  assert.equal(summary.totalEntryCount, 12)
  assert.equal(summary.missingCellCount, 2)
  assert.equal(summary.draftRate, 25)
  assert.equal(summary.tone, 'warning')
})

test('buildLiveRealityStatus explains active fill date and MES machine binding', () => {
  const summary = buildLiveRealityStatus({
    business_date: '2026-05-12',
    business_date_context: {
      requested_business_date: '2026-05-12',
      current_business_date: '2026-05-13',
      active_business_date: '2026-05-12',
      active_date_source: 'recent_upload',
      latest_fill_business_date: '2026-05-12',
      requested_entry_count: 36,
      current_date_entry_count: 0,
      active_date_entry_count: 36,
      has_current_date_entries: false,
      is_requested_current_date: false,
      is_showing_active_business_date: true,
    },
    mes_machine_binding: {
      mes_row_count: 21,
      route_inferred_machine_count: 8,
      upstream_machine_code_missing_count: 21,
      fill_entries_with_mes_match: 22,
      fill_entries_bound_to_machine: 22,
      fill_entries_pending_machine: 0,
    },
    overall_progress: {
      total_entry_count: 36,
    },
  })

  assert.equal(summary.tone, 'warning')
  assert.equal(summary.primaryLabel, '当前显示 2026-05-12')
  assert.equal(summary.currentDateLabel, '今天 2026-05-13 暂无填报')
  assert.equal(summary.activeDateLabel, '最近有效日 2026-05-12 · 36 卷')
  assert.equal(summary.fillLabel, '填报端 36 卷')
  assert.equal(summary.mesLabel, '外部 MES 21 行')
  assert.equal(summary.matchLabel, '匹配填报 22 卷')
  assert.equal(summary.bindingLabel, '已绑机列 22 卷')
  assert.equal(summary.routeLabel, '路线推断 8 行')
  assert.equal(summary.upstreamLabel, '上游机列码缺失 21 行')
  assert.equal(summary.pendingLabel, '待归属 0 卷')
})

test('shouldSwitchToRealtimeBusinessDate follows recent fill uploads when current day is empty', () => {
  const shouldSwitch = shouldSwitchToRealtimeBusinessDate({
    targetDate: '2026-05-13',
    eventBusinessDate: '2026-05-12',
    aggregation: {
      business_date: '2026-05-13',
      business_date_context: {
        requested_business_date: '2026-05-13',
        current_business_date: '2026-05-13',
        requested_entry_count: 0,
        current_date_entry_count: 0,
      },
    },
  })

  assert.equal(shouldSwitch, true)
})

test('shouldSwitchToRealtimeBusinessDate keeps manual historical dates stable', () => {
  const shouldSwitch = shouldSwitchToRealtimeBusinessDate({
    targetDate: '2026-05-11',
    eventBusinessDate: '2026-05-12',
    autoMode: false,
    aggregation: {
      business_date: '2026-05-11',
      business_date_context: {
        requested_business_date: '2026-05-11',
        current_business_date: '2026-05-13',
        requested_entry_count: 21,
        current_date_entry_count: 0,
      },
    },
  })

  assert.equal(shouldSwitch, false)
})

test('shouldRedirectToActiveBusinessDate follows aggregation context when today is empty', () => {
  const redirectDate = shouldRedirectToActiveBusinessDate({
    targetDate: '2026-05-13',
    autoMode: true,
    aggregation: {
      business_date: '2026-05-13',
      business_date_context: {
        requested_business_date: '2026-05-13',
        current_business_date: '2026-05-13',
        active_business_date: '2026-05-12',
        requested_entry_count: 0,
        current_date_entry_count: 0,
        active_date_entry_count: 39,
      },
    },
  })

  assert.equal(redirectDate, '2026-05-12')
})

test('buildPendingAssignmentSummary exposes draft coils missing machine ownership', () => {
  const summary = buildPendingAssignmentSummary({
    overall_progress: {
      pending_assignment: {
        entry_count: 17,
        draft_entry_count: 17,
        formal_entry_count: 0,
        missing_machine_count: 17,
        missing_shift_count: 0,
        workshop_count: 3,
        shift_count: 1,
        output: 120.46,
        rows: [
          {
            workshop_name: '2050冷轧车间',
            shift_name: '夜班',
            entry_count: 9,
            output: 77.21,
          },
          {
            workshop_name: '精整车间',
            shift_name: '夜班',
            entry_count: 4,
            output: 37.25,
          },
        ],
      },
    },
  })

  assert.equal(summary.entryCount, 17)
  assert.equal(summary.draftEntryCount, 17)
  assert.equal(summary.missingMachineCount, 17)
  assert.equal(summary.workshopCount, 3)
  assert.equal(summary.output, 120.46)
  assert.equal(summary.rows.length, 2)
  assert.equal(summary.rows[0].workshopName, '2050冷轧车间')
  assert.equal(summary.rows[0].shiftName, '夜班')
  assert.equal(summary.rows[0].entryCount, 9)
  assert.equal(summary.tone, 'warning')
})

test('buildMissingOutputWeightSummary exposes submitted coils missing output weight', () => {
  const summary = buildMissingOutputWeightSummary({
    data_quality: {
      missing_output_weight: {
        entry_count: 6,
        input: 32.4,
        scrap: 7.5,
        items: [
          {
            entry_id: 297,
            work_order_id: 273,
            tracking_card_no: 'S-2-062-1',
            workshop_name: '铸三车间',
            machine_name: '2#机',
            shift_name: '小夜',
            input_weight: 2.4,
            scrap_weight: 0,
            entry_status: 'submitted',
          },
        ],
      },
    },
  })

  assert.equal(summary.entryCount, 6)
  assert.equal(summary.input, 32.4)
  assert.equal(summary.scrap, 7.5)
  assert.equal(summary.tone, 'danger')
  assert.equal(summary.items[0].entryId, 297)
  assert.equal(summary.items[0].trackingCardNo, 'S-2-062-1')
  assert.equal(summary.items[0].workshopName, '铸三车间')
  assert.equal(summary.items[0].machineName, '2#机')
  assert.equal(summary.items[0].shiftName, '小夜')
})

test('buildWorkshopFillIntakeRows ranks draft pressure and keeps missing-only workshops', () => {
  const rows = buildWorkshopFillIntakeRows([
    {
      workshop_name: '包装车间',
      workshop_total: {
        formal_entry_count: 0,
        draft_entry_count: 0,
        total_entry_count: 0,
      },
      machines: [
        {
          shifts: [
            { is_applicable: true, submission_status: 'not_started' },
            { is_applicable: true, submission_status: 'not_started' },
          ],
        },
      ],
    },
    {
      workshop_name: '精整车间',
      workshop_total: {
        formal_entry_count: 0,
        draft_entry_count: 5,
        total_entry_count: 5,
      },
      machines: [
        {
          shifts: [
            { is_applicable: true, submission_status: 'not_started' },
          ],
        },
      ],
    },
  ])

  assert.equal(rows.length, 2)
  assert.equal(rows[0].workshopName, '精整车间')
  assert.equal(rows[0].draftRate, 83.33)
  assert.equal(rows[0].missingRate, 16.67)
  assert.equal(rows[0].tone, 'warning')
  assert.equal(rows[1].workshopName, '包装车间')
  assert.equal(rows[1].missingRate, 100)
  assert.equal(rows[1].tone, 'danger')
})

test('data source labels expose local coil fill as direct entry', () => {
  assert.equal(dataSourceLabel('local_shift_data'), '卷级直录')
  assert.equal(dataSourceLabel('mixed'), 'MES + 填报')
})

test('live dashboard resolves active business date before first load', () => {
  assert.match(liveDashboardSource, /fetchLiveActiveDate/)
  assert.match(liveDashboardSource, /initializeActiveBusinessDate/)
  assert.match(liveDashboardSource, /shouldRedirectToActiveBusinessDate/)
  assert.match(liveDashboardSource, /const redirectDate = shouldRedirectToActiveBusinessDate/)
  assert.match(liveDashboardSource, /targetDate\.value = redirectDate/)
  assert.match(liveDashboardSource, /onMounted\(async \(\) => \{\s*await initializeActiveBusinessDate\(\)\s*await loadDashboardSurface\(\)\s*\}\)/)
  assert.doesNotMatch(liveDashboardSource, /if \(!dateChanged\)/)
})

test('live dashboard publishes realtime aggregation before secondary cards settle', () => {
  const liveDataIndex = liveDashboardSource.indexOf('const liveData = await fetchLiveAggregation')
  const publishIndex = liveDashboardSource.indexOf('aggregation.value = liveData')
  const secondaryIndex = liveDashboardSource.indexOf('Promise.allSettled')

  assert.notEqual(liveDataIndex, -1)
  assert.notEqual(publishIndex, -1)
  assert.notEqual(secondaryIndex, -1)
  assert.ok(liveDataIndex < publishIndex)
  assert.ok(publishIndex < secondaryIndex)
})

test('buildOutputDistribution ranks live machine output and marks unbound lines', () => {
  const rows = buildOutputDistribution([
    {
      workshop_name: '2050冷轧车间',
      machines: [
        {
          machine_id: -5003,
          machine_name: '未绑定机列 / 夜班',
          day_total: { output: 74110 },
          shifts: [
            { shift_name: '白班', total_output: 0 },
            { shift_name: '夜班', total_output: 74110 },
          ],
        },
        {
          machine_id: 12,
          machine_name: '2#轧机',
          day_total: { output: 9100 },
          shifts: [{ shift_name: '白班', total_output: 9100 }],
        },
      ],
    },
    {
      workshop_name: '精整车间',
      machines: [
        {
          machine_id: -8003,
          machine_name: '未绑定机列 / 夜班',
          day_total: { output: 37250 },
          shifts: [{ shift_name: '夜班', total_output: 37250 }],
        },
      ],
    },
  ], 2)

  assert.equal(rows.length, 2)
  assert.equal(rows[0].workshopName, '2050冷轧车间')
  assert.equal(rows[0].machineName, '未绑定机列 / 夜班')
  assert.equal(rows[0].bindingLabel, '未绑定')
  assert.equal(rows[0].share, 100)
  assert.equal(rows[0].shiftLabel, '夜班')
  assert.equal(rows[1].output, 37250)
  assert.equal(rows[1].share, 50.26)
})

test('buildShiftOutputRhythm groups live output by shift rhythm', () => {
  const rows = buildShiftOutputRhythm([
    {
      workshop_id: 5,
      workshop_name: '2050冷轧车间',
      machines: [
        {
          machine_id: -5001,
          machine_name: '未绑定机列 / 白班',
          shifts: [{ shift_name: '白班', total_output: 9100, total_input: 9800 }],
        },
        {
          machine_id: -5003,
          machine_name: '未绑定机列 / 夜班',
          shifts: [{ shift_name: '夜班', total_output: 74110, total_input: 78100 }],
        },
      ],
    },
    {
      workshop_id: 8,
      workshop_name: '精整车间',
      machines: [
        {
          machine_id: -8003,
          machine_name: '未绑定机列 / 夜班',
          shifts: [{ shift_name: '夜班', total_output: 37250, total_input: 38900 }],
        },
      ],
    },
  ])

  assert.equal(rows.length, 2)
  assert.equal(rows[0].shiftName, '夜班')
  assert.equal(rows[0].output, 111360)
  assert.equal(rows[0].input, 117000)
  assert.equal(rows[0].machineCount, 2)
  assert.equal(rows[0].share, 92.45)
  assert.equal(rows[1].shiftName, '白班')
  assert.equal(rows[1].machineCount, 1)
  assert.equal(rows[1].share, 7.55)
})

test('buildUnboundFillSummary totals direct entries that still need machine ownership', () => {
  const summary = buildUnboundFillSummary([
    {
      workshop_id: 5,
      workshop_name: '2050冷轧车间',
      machines: [
        {
          machine_id: -5001,
          machine_name: '未绑定机列 / 白班',
          machine_binding_status: 'unbound',
          day_total: { output: 9100, input: 9800 },
          shifts: [{ shift_name: '白班', total_output: 9100, total_input: 9800 }],
        },
        {
          machine_id: -5003,
          machine_name: '未绑定机列 / 夜班',
          day_total: { output: 74110, input: 78100 },
          shifts: [{ shift_name: '夜班', total_output: 74110, total_input: 78100 }],
        },
        {
          machine_id: 5021,
          machine_name: '已绑定 1#线',
          machine_binding_status: 'bound',
          day_total: { output: 6000, input: 6500 },
          shifts: [{ shift_name: '白班', total_output: 6000, total_input: 6500 }],
        },
      ],
    },
    {
      workshop_id: 8,
      workshop_name: '精整车间',
      machines: [
        {
          machine_id: -8003,
          machine_name: '未绑定机列 / 夜班',
          machineBindingStatus: 'unbound',
          day_total: { output: 37250, input: 38900 },
          shifts: [{ shift_name: '夜班', total_output: 37250, total_input: 38900 }],
        },
      ],
    },
  ])

  assert.equal(summary.rowCount, 3)
  assert.equal(summary.workshopCount, 2)
  assert.equal(summary.shiftCount, 2)
  assert.equal(summary.output, 120460)
  assert.equal(summary.input, 126800)
  assert.equal(summary.rows[0].workshopName, '2050冷轧车间')
  assert.equal(summary.rows[0].shiftLabel, '夜班')
  assert.equal(summary.rows[0].output, 74110)
})

test('buildMachineOwnershipSummary separates bound output from unbound fill output', () => {
  const summary = buildMachineOwnershipSummary([
    {
      workshop_name: '2050冷轧车间',
      machines: [
        {
          machine_id: 5021,
          machine_name: '1#轧机',
          machine_binding_status: 'bound',
          day_total: { output: 50000, input: 53000 },
        },
        {
          machine_id: -5003,
          machine_name: '未绑定机列 / 夜班',
          day_total: { output: 74110, input: 78100 },
        },
      ],
    },
    {
      workshop_name: '精整车间',
      machines: [
        {
          machine_id: -8003,
          machine_name: '未绑定机列 / 夜班',
          machineBindingStatus: 'unbound',
          day_total: { output: 46350, input: 48700 },
        },
        {
          machine_id: 8008,
          machine_name: '无产出机列',
          machine_binding_status: 'bound',
          day_total: { output: 0, input: 1200 },
        },
      ],
    },
  ])

  assert.equal(summary.totalOutput, 170460)
  assert.equal(summary.boundOutput, 50000)
  assert.equal(summary.unboundOutput, 120460)
  assert.equal(summary.machineCount, 3)
  assert.equal(summary.boundMachineCount, 1)
  assert.equal(summary.unboundMachineCount, 2)
  assert.equal(summary.ownershipRate, 29.33)
  assert.equal(summary.unboundRate, 70.67)
  assert.equal(summary.needsBinding, true)
})

test('status helpers map submission and attendance states to readable tones', () => {
  assert.equal(statusToneForCell({ submission_status: 'all_submitted', is_applicable: true }), 'success')
  assert.equal(statusTextForCell({ submission_status: 'all_submitted', is_applicable: true }), '已填')

  assert.equal(statusToneForCell({ submission_status: 'in_progress', is_applicable: true }), 'warning')
  assert.equal(statusTextForCell({ submission_status: 'in_progress', is_applicable: true }), '进行中')

  assert.equal(statusToneForCell({ submission_status: 'not_started', is_applicable: true }), 'danger')
  assert.equal(statusTextForCell({ submission_status: 'not_started', is_applicable: true }), '缺报')

  assert.equal(statusToneForCell({ submission_status: 'all_submitted', is_applicable: true, attendance_exception_count: 1 }), 'danger')
  assert.equal(statusTextForCell({ submission_status: 'all_submitted', is_applicable: true, attendance_exception_count: 1 }), '考勤异常')

  assert.equal(statusToneForCell({ submission_status: 'all_submitted', is_applicable: true, attendance_status: 'not_started' }), 'warning')
  assert.equal(statusTextForCell({ submission_status: 'all_submitted', is_applicable: true, attendance_status: 'not_started' }), '考勤待确认')

  assert.equal(statusToneForCell({ submission_status: 'not_applicable', is_applicable: false }), 'muted')
  assert.equal(statusTextForCell({ submission_status: 'not_applicable', is_applicable: false }), '不适用')
})

test('sortWorkshopsForCommandCenter puts workshops needing attention first', () => {
  const workshops = [
    {
      workshop_id: 1,
      workshop_name: '已完成车间',
      machines: [
        {
          shifts: [
            { is_applicable: true, submission_status: 'all_submitted' },
          ],
        },
      ],
    },
    {
      workshop_id: 2,
      workshop_name: '缺报车间',
      machines: [
        {
          shifts: [
            { is_applicable: true, submission_status: 'not_started' },
            { is_applicable: true, submission_status: 'in_progress' },
          ],
        },
      ],
    },
  ]

  assert.equal(sortWorkshopsForCommandCenter(workshops)[0].workshop_name, '缺报车间')
})

test('manageNavGroups keeps the manager surface focused on daily factory work', () => {
  const groups = manageNavGroups({
    canAccessReviewSurface: true,
    reviewSurface: true,
    canAccessDesktopConfig: false,
    adminSurface: false,
    isAdmin: false,
  })

  assert.deepEqual(groups.map((group) => group.label), ['工厂状态', '经营效益', '异常质量', 'AI 助手'])
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.path === '/manage/factory/cost'), true)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.shortLabel === '成本效益'), false)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.title === '异常与补录'), true)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.shortLabel === 'AI 助手'), true)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.path === '/manage/reports'), false)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.path === '/manage/admin/settings'), false)
})

test('management shell components do not render numeric module badges', () => {
  assert.doesNotMatch(referenceFrameSource, /reference-page__number/)
  assert.doesNotMatch(referenceCardSource, /reference-card__number/)
  assert.doesNotMatch(moduleTileSource, /xt-module-tile__number/)
  assert.doesNotMatch(routerSource, /xt-placeholder-page__number/)
})

test('reference page frame uses canonical product identity', () => {
  assert.match(referenceFrameSource, /鑫泰铝业 数据中枢 · 运行中心/)
  assert.doesNotMatch(referenceFrameSource, /鑫泰数据中枢 · 运行中心/)
})

test('LiveDashboard first screen uses management-readable labels', () => {
  assert.match(liveDashboardSource, /今日产量/)
  assert.match(liveDashboardSource, /损耗重量/)
  assert.match(liveDashboardSource, /成材率/)
  assert.match(liveDashboardSource, /毛利估算|亏损估算/)
  assert.match(liveDashboardSource, /风险项/)
  assert.match(liveDashboardSource, /外部 MES/)
  assert.match(liveDashboardSource, /fetchMesSyncStatus/)
  assert.match(liveDashboardSource, /fetchMesSyncRuns/)
  assert.match(liveDashboardSource, /MES 同步稳定性/)
  assert.match(liveDashboardSource, /mes-sync-stability/)
  assert.match(liveDashboardSource, /mesSyncRunSummary/)
  assert.match(liveDashboardSource, /MES_MVC_BASE_URL/)
  assert.match(liveDashboardSource, /required_env|requiredEnv/)
  assert.match(liveDashboardSource, /mesRequiredEnvLabel/)
  assert.match(liveDashboardSource, /缺少配置/)
  assert.match(liveDashboardSource, /fetchExternalReadiness/)
  assert.match(liveDashboardSource, /externalReadiness/)
  assert.match(liveDashboardSource, /externalReadinessLoaded/)
  assert.match(liveDashboardSource, /外部联通闸门/)
  assert.match(liveDashboardSource, /外部联通明细/)
  assert.match(liveDashboardSource, /external-readiness-lanes/)
  assert.match(liveDashboardSource, /externalReadinessLanes/)
  assert.match(liveDashboardSource, /missing_inputs|missingInputs/)
  assert.match(liveDashboardSource, /missing_fields|missingFields/)
  assert.match(liveDashboardSource, /externalMissingInputs/)
  assert.match(liveDashboardSource, /external-readiness-missing/)
  assert.match(liveDashboardSource, /缺失输入清单/)
  assert.match(liveDashboardSource, /建议取值/)
  assert.match(liveDashboardSource, /LLM_DISABLED/)
  assert.match(liveDashboardSource, /APP_CONNECTION_DISABLED/)
  assert.match(liveDashboardSource, /DINGTALK_NO_BOUND_USERS/)
  assert.match(liveDashboardSource, /LLM 摘要/)
  assert.match(liveDashboardSource, /应用连接/)
  assert.match(liveDashboardSource, /钉钉人员/)
  assert.doesNotMatch(liveDashboardSource, /保存密钥|写入配置|启用外联|重置同步|强制同步/)
  assert.match(liveDashboardSource, /接口待返回/)
  assert.match(liveDashboardSource, /hard_issues|hardIssues/)
  assert.match(liveDashboardSource, /live-output-distribution/)
  assert.match(liveDashboardSource, /卷级直录分布/)
  assert.match(liveDashboardSource, /outputDistributionRows/)
  assert.match(liveDashboardSource, /live-shift-rhythm/)
  assert.match(liveDashboardSource, /班次产量节奏/)
  assert.match(liveDashboardSource, /shiftOutputRhythmRows/)
  assert.match(liveDashboardSource, /未绑定填报归属/)
  assert.match(liveDashboardSource, /unboundFillSummary/)
  assert.match(liveDashboardSource, /live-unbound-fill/)
  assert.match(liveDashboardSource, /绑定账号/)
  assert.match(liveDashboardSource, /unboundAccountRoute/)
  assert.match(liveDashboardSource, /machine_binding: 'unbound'/)
  assert.match(liveDashboardSource, /机列归属率/)
  assert.match(liveDashboardSource, /machineOwnershipSummary/)
  assert.match(liveDashboardSource, /live-machine-ownership/)
  assert.match(liveDashboardSource, /buildMachineOwnershipSummary/)
  assert.match(liveDashboardSource, /填报接入/)
  assert.match(liveDashboardSource, /已进入正式/)
  assert.match(liveDashboardSource, /草稿待提交/)
  assert.match(liveDashboardSource, /fillIntakeSummary/)
  assert.match(liveDashboardSource, /buildFillIntakeSummary/)
  assert.match(liveDashboardSource, /车间填报接入/)
  assert.match(liveDashboardSource, /workshopFillIntakeRows/)
  assert.match(liveDashboardSource, /fill-workshop-flow/)
  assert.match(liveDashboardSource, /buildWorkshopFillIntakeRows/)
  assert.match(liveDashboardSource, /实时数据日期/)
  assert.match(liveDashboardSource, /外部 MES 机列绑定/)
  assert.match(liveDashboardSource, /live-reality-strip/)
  assert.match(liveDashboardSource, /liveRealityStatus/)
  assert.match(liveDashboardSource, /buildLiveRealityStatus/)
  assert.match(liveDashboardSource, /草稿待归属/)
  assert.match(liveDashboardSource, /pendingAssignmentSummary/)
  assert.match(liveDashboardSource, /buildPendingAssignmentSummary/)
  assert.match(liveDashboardSource, /待补产出重量/)
  assert.match(liveDashboardSource, /missingOutputWeightSummary/)
  assert.match(liveDashboardSource, /live-missing-output/)
  assert.match(liveDashboardSource, /buildMissingOutputWeightSummary/)
  assert.match(liveDashboardSource, /补重量/)
  assert.match(liveDashboardSource, /补产出重量/)
  assert.match(liveDashboardSource, /missingOutputDialogVisible/)
  assert.match(liveDashboardSource, /activeMissingOutput/)
  assert.match(liveDashboardSource, /resolveMissingOutputWeight/)
  assert.match(liveDashboardSource, /submitMissingOutputWeight/)
  assert.match(liveDashboardSource, /el-input-number/)
  assert.match(liveDashboardSource, /经营链路/)
  assert.match(liveDashboardSource, /blockerBreakdown/)
  assert.match(liveDashboardSource, /deliveryBlocker/)
  assert.match(liveDashboardSource, /Promise\.allSettled/)
  assert.match(liveDashboardSource, /storageFinishedWeight/)
  assert.match(liveDashboardSource, /shipmentWeight/)
  assert.match(liveDashboardSource, /入库\/发货[\s\S]*storageFinishedWeight[\s\S]*shipmentWeight/)
  assert.doesNotMatch(liveDashboardSource, /<span>入库\/发货<\/span>[\s\S]{0,160}deliveryReady/)
})

test('realtime api exposes missing output weight correction endpoint', () => {
  assert.match(realtimeApiSource, /resolveMissingOutputWeight/)
  assert.match(realtimeApiSource, /api\.patch/)
  assert.match(realtimeApiSource, /\/aggregation\/live\/missing-output\/\$\{entryId\}/)
  assert.match(realtimeApiSource, /skipErrorToast:\s*true/)
})

test('CostAccountingCenter starts with a readable operating ledger', () => {
  assert.match(costCenterSource, /收入估算/)
  assert.match(costCenterSource, /成本估算/)
  assert.match(costCenterSource, /毛利估算/)
  assert.match(costCenterSource, /每吨成本/)
  assert.doesNotMatch(costCenterSource, /revenuePerTon:\s*1200/)
  assert.match(costCenterSource, /process-mobile-list/)
  assert.match(costCenterSource, /高级参数/)
})

test('CostAccountingCenter can persist generated cost table snapshots', () => {
  assert.match(executiveApiSource, /saveCostStrategySnapshot/)
  assert.match(executiveApiSource, /api\.post\('\/executive\/cost-strategy-snapshots'/)
  assert.match(executiveApiSource, /tableModels/)
  assert.match(costCenterSource, /saveCostStrategySnapshot/)
  assert.match(costCenterSource, /data-testid="cost-snapshot-save"/)
  assert.match(costCenterSource, /保存快照/)
  assert.match(costCenterSource, /snapshotSaving/)
  assert.match(costCenterSource, /snapshotSavedAt/)
  assert.match(costCenterSource, /canPersistSnapshot/)
  assert.match(costCenterSource, /useAuthStore/)
  assert.match(costCenterSource, /handleSaveSnapshot/)
})

test('LiveDashboard keeps the command matrix contained on narrow screens', () => {
  assert.match(liveDashboardSource, /class="live-dashboard__export-button"/)
  assert.match(liveDashboardSource, /aria-label="导出电子表格"/)
  assert.match(liveDashboardSource, /\.live-dashboard__workshops\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-dashboard__collapse\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-workshop__board\s*{[^}]*overflow:\s*hidden/s)
  assert.match(liveDashboardSource, /\.live-board__scroller\s*{[^}]*max-width:\s*100%/s)
})
