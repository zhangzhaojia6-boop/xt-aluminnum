import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { manageNavGroups } from '../src/config/manage-navigation.js'
import {
  buildCommandCenterSummary,
  sortWorkshopsForCommandCenter,
  statusTextForCell,
  statusToneForCell,
} from '../src/utils/managementCommandCenter.js'

const liveDashboardSource = readFileSync(
  new URL('../src/views/reports/LiveDashboard.vue', import.meta.url),
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

  assert.deepEqual(groups.map((group) => group.label), ['总览', '工厂状态', '填报审核', '日报交付', '异常质量'])
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.shortLabel === 'AI 工作台'), false)
  assert.equal(groups.flatMap((group) => group.items).some((item) => item.path === '/manage/admin/settings'), false)
})

test('LiveDashboard keeps the command matrix contained on narrow screens', () => {
  assert.match(liveDashboardSource, /class="live-dashboard__export-button"/)
  assert.match(liveDashboardSource, /aria-label="导出电子表格"/)
  assert.match(liveDashboardSource, /\.live-dashboard__workshops\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-dashboard__collapse\s*{[^}]*min-width:\s*0/s)
  assert.match(liveDashboardSource, /\.live-workshop__board\s*{[^}]*overflow:\s*hidden/s)
  assert.match(liveDashboardSource, /\.live-board__scroller\s*{[^}]*max-width:\s*100%/s)
})
