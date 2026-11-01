import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'
import { setupStoredFillOnlySession } from './helpers/fill-only-session'

const baseTimestamp = '2026-04-23T08:00:00Z'

function currentBusinessDate() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function createQualityIssue(overrides = {}) {
  return {
    id: 11,
    business_date: currentBusinessDate(),
    issue_type: 'invalid_value',
    source_type: 'production',
    dimension_key: 'workshop:ZR2|machine:ZD-1',
    field_name: '成材率',
    issue_level: 'warning',
    issue_desc: '成材率低于阈值',
    status: 'open',
    resolved_by: null,
    resolved_at: null,
    resolve_note: null,
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

async function setupQualityMocks(page, initialIssues = [createQualityIssue()]) {
  const requests = {
    runChecks: [],
    resolve: [],
    ignore: []
  }
  const issues = initialIssues.map((issue) => ({ ...issue }))

  await page.route('**/api/v1/quality/issues**', async (route) => {
    const url = new URL(route.request().url())
    const issueId = url.searchParams.get('issue_id')
    const businessDate = url.searchParams.get('business_date')
    const issueType = url.searchParams.get('issue_type')
    const issueLevel = url.searchParams.get('issue_level')
    const status = url.searchParams.get('status')
    let responseIssues = issues

    if (issueId) responseIssues = responseIssues.filter((issue) => String(issue.id) === issueId)
    if (businessDate) responseIssues = responseIssues.filter((issue) => issue.business_date === businessDate)
    if (issueType) responseIssues = responseIssues.filter((issue) => issue.issue_type === issueType)
    if (issueLevel) responseIssues = responseIssues.filter((issue) => issue.issue_level === issueLevel)
    if (status) responseIssues = responseIssues.filter((issue) => issue.status === status)

    await fulfillJson(route, responseIssues)
  })

  await page.route('**/api/v1/quality/run-checks', async (route) => {
    const body = route.request().postDataJSON()
    requests.runChecks.push(body)
    const generatedIssue = createQualityIssue({
      id: 12,
      business_date: body.business_date,
      issue_type: 'missing_data',
      source_type: 'mobile',
      dimension_key: 'workshop:ZR2|machine:ZD-2',
      field_name: '产出重量',
      issue_level: 'blocker',
      issue_desc: '机列主操产量缺失'
    })
    issues.push(generatedIssue)
    await fulfillJson(route, [generatedIssue])
  })

  for (const action of ['resolve', 'ignore']) {
    await page.route(`**/api/v1/quality/issues/*/${action}`, async (route) => {
      const body = route.request().postDataJSON()
      requests[action].push(body)
      const match = route.request().url().match(/\/issues\/(\d+)\/[^/]+$/)
      const issue = issues.find((candidate) => String(candidate.id) === match?.[1])
      const nextStatus = action === 'resolve' ? 'resolved' : 'ignored'

      if (issue) {
        issue.status = nextStatus
        issue.resolve_note = body.note
        issue.resolved_by = 1
        issue.resolved_at = '2026-04-23T09:00:00Z'
        issue.updated_at = issue.resolved_at
      }

      await fulfillJson(route, issue)
    })
  }

  return { requests }
}

// 质量与告警中心列表、运行检查、解决和忽略已随改版并入异常页（旧地址见 review-runtime.spec.js），这里只保留仍在的详情页
test('quality issue detail page shows the issue', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await setupQualityMocks(page)

  await page.goto('/manage/quality/detail/11')

  await expect(page.getByRole('heading', { name: '质量问题详情' })).toBeVisible()
  await expect(page.getByText('数值异常')).toBeVisible()
  await expect(page.getByText('生产系统')).toBeVisible()
  await expect(page.getByText('成材率', { exact: true })).toBeVisible()
  await expect(page.getByText('成材率低于阈值')).toBeVisible()
})

test('fill-only operator cannot access quality center', async ({ page }) => {
  await setupStoredFillOnlySession(page)
  await setupQualityMocks(page)

  await page.goto('/manage/quality')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '质量与告警中心' })).toHaveCount(0)
})
