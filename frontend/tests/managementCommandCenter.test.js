import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { manageNavGroups } from '../src/config/manage-navigation.js'
import {
  buildCommandCenterSummary,
  buildOutputDistribution,
  buildShiftOutputRhythm,
  buildUnboundFillSummary,
  dataSourceLabel,
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

const baseAggregation = {
  overall_progress: {
    submitted_cells: 4,
    total_cells: 8,
    missing_cell_count: 2,
    attention_cell_count: 3,
    completion_rate: 50,
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

test('data source labels expose local coil fill as direct entry', () => {
  assert.equal(dataSourceLabel('local_shift_data'), '卷级直录')
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
  assert.match(liveDashboardSource, /MES_MVC_BASE_URL/)
  assert.match(liveDashboardSource, /required_env|requiredEnv/)
  assert.match(liveDashboardSource, /mesRequiredEnvLabel/)
  assert.match(liveDashboardSource, /缺少配置/)
  assert.match(liveDashboardSource, /fetchExternalReadiness/)
  assert.match(liveDashboardSource, /externalReadiness/)
  assert.match(liveDashboardSource, /externalReadinessLoaded/)
  assert.match(liveDashboardSource, /外部联通闸门/)
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
  assert.match(liveDashboardSource, /经营链路/)
  assert.match(liveDashboardSource, /blockerBreakdown/)
  assert.match(liveDashboardSource, /deliveryBlocker/)
  assert.match(liveDashboardSource, /Promise\.allSettled/)
  assert.match(liveDashboardSource, /storageFinishedWeight/)
  assert.match(liveDashboardSource, /shipmentWeight/)
  assert.match(liveDashboardSource, /入库\/发货[\s\S]*storageFinishedWeight[\s\S]*shipmentWeight/)
  assert.doesNotMatch(liveDashboardSource, /<span>入库\/发货<\/span>[\s\S]{0,160}deliveryReady/)
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

test('LiveDashboard keeps the command matrix contained on narrow screens', () => {
  assert.match(liveDashboardSource, /class="live-dashboard__export-button"/)
  assert.match(liveDashboardSource, /aria-label="导出电子表格"/)
  assert.match(liveDashboardSource, /\.live-dashboard__workshops\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-dashboard__collapse\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-workshop__board\s*{[^}]*overflow:\s*hidden/s)
  assert.match(liveDashboardSource, /\.live-board__scroller\s*{[^}]*max-width:\s*100%/s)
})
