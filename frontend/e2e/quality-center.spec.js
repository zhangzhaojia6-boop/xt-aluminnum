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

async function submitDispositionNote(page, { rowText, actionLabel, note }) {
  const row = page.locator('.el-table__row', { hasText: rowText })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: actionLabel }).click()

  const messageBox = page.locator('.el-message-box').last()
  await expect(messageBox).toBeVisible()
  await messageBox.locator('.el-message-box__input input').fill(note)
  await messageBox.getByRole('button', { name: '提交' }).click()
  await expect(page.locator('.el-message-box')).toHaveCount(0)
}

test('quality center lists issues and opens detail', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await setupQualityMocks(page)

  await page.goto('/manage/quality')

  const center = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '质量与告警中心' }) })
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(center.getByRole('heading', { name: '质量与告警中心' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '业务日期' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '问题级别' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '处理状态' })).toBeVisible()
  await expect(center.getByText('成材率低于阈值')).toBeVisible()
  await expect(center.getByText('workshop:ZR2|machine:ZD-1')).toBeVisible()
  await expect(center.getByText('成材率', { exact: true })).toBeVisible()
  await expect(center.getByText('预警')).toBeVisible()

  await center.locator('.el-table__row', { hasText: '成材率低于阈值' }).getByRole('button', { name: '详情' }).click()

  await expect(page).toHaveURL(/\/manage\/quality\/detail\/11$/)
  await expect(page.getByRole('heading', { name: '质量问题详情' })).toBeVisible()
  await expect(page.getByText('数值异常')).toBeVisible()
  await expect(page.getByText('生产系统')).toBeVisible()
  await expect(page.getByText('成材率', { exact: true })).toBeVisible()
  await expect(page.getByText('成材率低于阈值')).toBeVisible()
})

test('quality center run-check uses selected business date and refreshes issues', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  const { requests } = await setupQualityMocks(page)

  await page.goto('/manage/quality')

  const center = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '质量与告警中心' }) })
  const businessDate = await center.locator('.el-date-editor input').first().inputValue()
  await center.getByRole('button', { name: '运行质量检查' }).click()

  await expect.poll(() => requests.runChecks).toHaveLength(1)
  expect(requests.runChecks[0].business_date).toBe(businessDate)
  await expect(center.getByText('workshop:ZR2|machine:ZD-2')).toBeVisible()
  await expect(center.getByText('产出重量')).toBeVisible()
  await expect(center.getByText('机列主操产量缺失')).toBeVisible()
})

for (const scenario of [
  {
    actionKey: 'resolve',
    actionLabel: '标记已解决',
    rowText: '已解决问题',
    statusLabel: '已解决',
    rawNote: '  质检复核后确认已补齐  ',
    expectedNote: '质检复核后确认已补齐'
  },
  {
    actionKey: 'ignore',
    actionLabel: '忽略问题',
    rowText: '忽略问题',
    statusLabel: '已忽略',
    rawNote: '重复导入批次，不纳入本次阻断',
    expectedNote: '重复导入批次，不纳入本次阻断'
  }
]) {
  test(`quality ${scenario.actionKey} sends operator note and updates status`, async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    const { requests } = await setupQualityMocks(page, [
      createQualityIssue({ id: 21, field_name: scenario.rowText, issue_desc: `${scenario.rowText}待处置` })
    ])

    await page.goto('/manage/quality')

    await submitDispositionNote(page, {
      rowText: scenario.rowText,
      actionLabel: scenario.actionLabel,
      note: scenario.rawNote
    })

    await expect.poll(() => requests[scenario.actionKey]).toHaveLength(1)
    expect(requests[scenario.actionKey][0].note).toBe(scenario.expectedNote)
    await expect(
      page.locator('.el-table__row', { hasText: scenario.rowText }).locator('.reference-status', {
        hasText: scenario.statusLabel
      })
    ).toBeVisible()
  })
}

test('fill-only operator cannot access quality center', async ({ page }) => {
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
  await setupQualityMocks(page)

  await page.goto('/manage/quality')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '质量与告警中心' })).toHaveCount(0)
})
