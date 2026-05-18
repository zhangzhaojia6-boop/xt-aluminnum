import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

import { clearAuthStorage } from '../helpers/mock-login'
import { setupReviewSessionAndMocks } from '../helpers/review-mocks'

const authPages = [
  { name: 'executive dashboard', path: '/manage/executive', scope: 'main', heading: '鑫泰铝业 数据中枢' },
  { name: 'factory dashboard', path: '/dashboard/factory', scope: 'main', testId: 'factory-dashboard' },
  { name: 'workshop dashboard', path: '/dashboard/workshop', scope: 'main', testId: 'workshop-dashboard' },
  { name: 'ingestion center', path: '/manage/ingestion', scope: 'main', heading: '数据接入与字段映射中心' },
  { name: 'review center', path: '/manage/entry-center?desktop=1', scope: '[data-testid="review-task-center"]', testId: 'review-task-center', mocks: setupReviewCenterMocks },
  { name: 'reports center', path: '/manage/reports', scope: 'main', heading: '日报与交付中心', mocks: setupReportsMocks },
  { name: 'quality center', path: '/manage/quality', scope: 'main', heading: '质量与告警中心', mocks: setupQualityMocks },
  { name: 'reconciliation center', path: '/manage/reconciliation', scope: 'main', heading: '差异核对中心', mocks: setupReconciliationMocks },
  { name: 'master center', path: '/manage/master', scope: 'main', heading: '车间主数据' },
  { name: 'mobile entry', path: '/entry', scope: '.mobile-shell', testId: 'mobile-entry' },
  {
    name: 'mobile shift report',
    path: '/mobile/report/2026-04-23/1',
    scope: '.mobile-shell',
    testId: 'mobile-shift-report-workspace',
    mocks: setupMobileReportMocks
  }
]

function formatColorViolations(violations) {
  return violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    help: violation.help,
    nodes: violation.nodes.map((node) => ({
      target: node.target,
      summary: node.failureSummary
    }))
  }))
}

async function expectNoColorContrastViolations(page, scope, name) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2aa', 'wcag21aa'])
    .include(scope)
    .analyze()

  const colorContrastViolations = results.violations.filter((violation) => violation.id === 'color-contrast')
  expect(
    colorContrastViolations,
    `${name} color contrast violations:\n${JSON.stringify(formatColorViolations(colorContrastViolations), null, 2)}`
  ).toEqual([])
}

async function expectPageReady(page, target) {
  if (target.testId) {
    await expect(page.getByTestId(target.testId)).toBeVisible()
    return
  }
  await expect(page.getByRole('heading', { name: target.heading })).toBeVisible()
}

async function setupReportsMocks(page) {
  await page.route(/.*\/api\/v1\/reports(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 31,
          report_date: '2026-04-23',
          report_type: 'production',
          report_data: {
            total_output_weight: 128.5,
            legacy_profile: { items: [] },
            yield_matrix_lane: { company_total_yield: 94.6 },
            mobile_reporting_summary: { reported_count: 7, unreported_count: 1 }
          },
          text_summary: '生产日报过程摘要',
          final_text_summary: '最终版生产日报已归档',
          status: 'published',
          is_final_version: true,
          quality_gate_status: 'ready',
          delivery_ready: true,
          generated_at: '2026-04-23T08:00:00Z'
        }
      ])
    })
  })
}

async function setupQualityMocks(page) {
  await page.route('**/api/v1/quality/issues**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 11,
          business_date: '2026-04-23',
          issue_type: 'invalid_value',
          source_type: 'production',
          dimension_key: 'workshop:ZR2|machine:ZD-1',
          field_name: '成材率',
          issue_level: 'warning',
          issue_desc: '成材率低于阈值',
          status: 'open',
          created_at: '2026-04-23T08:00:00Z',
          updated_at: '2026-04-23T08:00:00Z'
        }
      ])
    })
  })
}

async function setupReconciliationMocks(page) {
  await page.route('**/api/v1/reconciliation/items**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 11,
          business_date: '2026-04-23',
          reconciliation_type: 'production_vs_mes',
          source_a: 'production',
          source_b: 'mes',
          dimension_key: 'XT-ZD-1',
          field_name: '产出重量',
          source_a_value: '1175',
          source_b_value: '1160',
          diff_value: 15,
          status: 'open',
          created_at: '2026-04-23T08:00:00Z',
          updated_at: '2026-04-23T08:00:00Z'
        }
      ])
    })
  })
}

async function setupReviewCenterMocks(page) {
  await page.route('**/api/v1/aggregation/live/active-date', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-05-12',
        source: 'recent_upload'
      })
    })
  })

  await page.route('**/api/v1/aggregation/live/pending-assignment**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        summary: {
          entry_count: 0,
          mes_matched_count: 0,
          unique_candidate_count: 0,
          ambiguous_candidate_count: 0,
          missing_shift_count: 0
        },
        items: [],
        total: 0
      })
    })
  })

  await page.route('**/api/v1/reconciliation/items**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([])
    })
  })
}

async function setupMobileReportMocks(page) {
  await page.route('**/api/v1/mobile/report/2026-04-23/1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-04-23',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '挤压车间',
        team_name: '甲班',
        leader_name: 'Playwright Admin',
        report_status: 'draft',
        attendance_count: 12,
        input_weight: 100,
        output_weight: 96,
        scrap_weight: 4,
        electricity_daily: 320,
        gas_daily: 18,
        machine_energy_records: [],
        active_reminders: [],
        workshop_machines: [],
        monthly_output: 1175,
        monthly_electricity: 3800,
        monthly_gas: 260,
        monthly_yield_rate: 96,
        compare_value: 92
      })
    })
  })
}

test.describe('contrast accessibility audit', () => {
  test('login page has no WCAG AA color contrast violations', async ({ page }) => {
    await clearAuthStorage(page)
    await page.goto('/login')
    await expect(page.getByTestId('login-page')).toBeVisible()
    await expectNoColorContrastViolations(page, '.login-stage', 'login page')
  })

  for (const target of authPages) {
    test(`${target.name} has no WCAG AA color contrast violations`, async ({ page }) => {
      await setupReviewSessionAndMocks(page)
      if (target.mocks) await target.mocks(page)
      await page.goto(target.path)
      await expectPageReady(page, target)
      await expectNoColorContrastViolations(page, target.scope, target.name)
    })
  }
})
