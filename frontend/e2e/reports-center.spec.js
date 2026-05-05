import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const baseTimestamp = '2026-04-23T08:00:00Z'

function currentBusinessDate() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function createReport(overrides = {}) {
  return {
    id: 31,
    report_date: currentBusinessDate(),
    report_type: 'production',
    workshop_id: null,
    report_data: {
      total_output_weight: 128.5,
      total_input_weight: 136.2,
      yield_rate: 94.3,
      total_attendance: 42,
      total_electricity_kwh: 3180,
      energy_per_ton: 24.7,
      total_expected: 8,
      reporting_rate: 96,
      anomaly_summary: { digest: '1 条异常待跟进' },
      legacy_profile: { items: [{ id: 'legacy-1' }, { id: 'legacy-2' }] },
      mobile_reporting_summary: {
        reported_count: 7,
        unreported_count: 1,
        returned_count: 0,
        late_count: 1
      },
      workshops: [
        {
          workshop_name: '熔铸车间',
          output_weight: 68.5,
          input_weight: 72.1,
          yield_rate: 95,
          attendance_count: 18,
          electricity_kwh: 1510
        }
      ],
      yield_matrix_lane: {
        business_date: currentBusinessDate(),
        company_total_yield: 94.6,
        mp_targets: { M: 95, P: 93 },
        snapshot_count: 6,
        quality_status: 'ready',
        primary_delivery_scope: 'factory',
        delivery_scopes: ['factory', 'workshop'],
        workshop_yields: {
          熔铸车间: 94.2,
          冷轧车间: 95.1
        }
      }
    },
    text_summary: '生产日报过程摘要',
    final_text_summary: '最终版生产日报已归档',
    generated_scope: 'include_reviewed',
    output_mode: 'both',
    status: 'published',
    generated_at: baseTimestamp,
    reviewed_by: 1,
    reviewed_at: '2026-04-23T08:30:00Z',
    published_by: 1,
    published_at: '2026-04-23T09:00:00Z',
    final_confirmed_by: 'admin',
    final_confirmed_at: '2026-04-23T09:10:00Z',
    is_final_version: true,
    quality_gate_status: 'ready',
    quality_gate_summary: '质量闸门通过',
    delivery_ready: true,
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
    ...overrides
  }
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })
}

async function setupReportsMocks(page, initialReports = [createReport()]) {
  const requests = {
    list: []
  }
  const reports = initialReports.map((report) => ({ ...report }))

  await page.route(/.*\/api\/v1\/reports(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url())
    const params = Object.fromEntries(url.searchParams.entries())
    const startDate = url.searchParams.get('start_date')
    const endDate = url.searchParams.get('end_date')
    const reportType = url.searchParams.get('report_type')
    const status = url.searchParams.get('status')
    let responseReports = reports

    requests.list.push(params)

    if (startDate) responseReports = responseReports.filter((report) => report.report_date >= startDate)
    if (endDate) responseReports = responseReports.filter((report) => report.report_date <= endDate)
    if (reportType) responseReports = responseReports.filter((report) => report.report_type === reportType)
    if (status) responseReports = responseReports.filter((report) => report.status === status)

    await fulfillJson(route, responseReports)
  })

  await page.route(/.*\/api\/v1\/reports\/(\d+)(?:\?.*)?$/, async (route) => {
    const match = route.request().url().match(/\/reports\/(\d+)(?:\?.*)?$/)
    const report = reports.find((candidate) => String(candidate.id) === match?.[1])
    await fulfillJson(route, report || null)
  })

  return { requests }
}

async function selectFilter(page, center, label, option) {
  await center.locator('.el-form-item', { hasText: label }).locator('.el-select__wrapper').click()
  await page.locator('.el-select-dropdown__item').filter({ hasText: option }).last().click()
}

test('reports center sends filters and opens report detail', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  const { requests } = await setupReportsMocks(page)

  await page.goto('/manage/reports')

  const center = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '日报与交付中心' }) })
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(center.getByRole('heading', { name: '日报与交付中心' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '报告日期' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '报告类型' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '当前状态' })).toBeVisible()
  await expect(center.getByText('生产日报')).toBeVisible()
  await expect(center.getByText('已发布')).toBeVisible()
  await expect(center.getByText('产量 128.5')).toBeVisible()
  await expect(center.getByText('旁路资料 2 份')).toBeVisible()

  await selectFilter(page, center, '报告类型', '生产日报')
  await selectFilter(page, center, '当前状态', '已发布')
  await center.getByRole('button', { name: '查询' }).click()

  await expect.poll(() => requests.list.length).toBeGreaterThanOrEqual(2)
  const latestQuery = requests.list.at(-1)
  expect(latestQuery.start_date).toBe(currentBusinessDate())
  expect(latestQuery.end_date).toBe(currentBusinessDate())
  expect(latestQuery.report_type).toBe('production')
  expect(latestQuery.status).toBe('published')

  await center.locator('.el-table__row', { hasText: '生产日报' }).getByRole('button', { name: '查看详情' }).click()

  await expect(page).toHaveURL(/\/manage\/reports\/detail\/31$/)
  await expect(page.getByRole('heading', { name: '日报详情' })).toBeVisible()
  await expect(page.getByText('生产日报', { exact: true })).toBeVisible()
  await expect(page.getByText('已发布')).toBeVisible()
  await expect(page.getByText('最终版生产日报已归档')).toBeVisible()
  await expect(page.getByText('总产量')).toBeVisible()
  await expect(page.getByText('128.5')).toBeVisible()
  await expect(page.getByText('熔铸车间').first()).toBeVisible()
  await expect(page.getByText('成品率矩阵正式口径')).toBeVisible()
  await expect(page.getByText('94.6').first()).toBeVisible()
  await expect(page.getByText('上报闭环')).toBeVisible()
  await expect(page.getByText('7', { exact: true }).first()).toBeVisible()
})

test('fill-only operator cannot access reports center', async ({ page }) => {
  await setupReviewSessionAndMocks(page, {
    token: 'playwright-fill-token',
    user: {
      id: 2,
      username: 'operator',
      name: 'Playwright Operator',
      role: 'operator',
      is_mobile_user: true,
      is_reviewer: false,
      is_manager: false,
      data_scope_type: 'self_team',
      assigned_shift_ids: []
    }
  })
  await setupReportsMocks(page)

  await page.goto('/manage/reports')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '日报与交付中心' })).toHaveCount(0)
})
