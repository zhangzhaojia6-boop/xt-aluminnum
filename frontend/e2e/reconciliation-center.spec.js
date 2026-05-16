import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const baseTimestamp = '2026-04-23T08:00:00Z'

function createReconciliationItem(overrides = {}) {
  return {
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

async function setupReconciliationMocks(page, initialItems = [createReconciliationItem()]) {
  const requests = {
    generate: [],
    confirm: [],
    ignore: [],
    correct: []
  }
  const items = initialItems.map((item) => ({ ...item }))

  await page.route('**/api/v1/reconciliation/items**', async (route) => {
    const url = new URL(route.request().url())
    const itemId = url.searchParams.get('item_id')
    const status = url.searchParams.get('status')
    const reconciliationType = url.searchParams.get('reconciliation_type')
    let responseItems = items

    if (itemId) responseItems = responseItems.filter((item) => String(item.id) === itemId)
    if (status) responseItems = responseItems.filter((item) => item.status === status)
    if (reconciliationType) {
      responseItems = responseItems.filter((item) => item.reconciliation_type === reconciliationType)
    }

    await fulfillJson(route, responseItems)
  })

  await page.route('**/api/v1/reconciliation/generate', async (route) => {
    const body = route.request().postDataJSON()
    requests.generate.push(body)
    const generatedItem = createReconciliationItem({
      id: 12,
      dimension_key: 'XT-ZD-2',
      field_name: '投入重量',
      source_a_value: '880',
      source_b_value: '872',
      diff_value: 8,
      business_date: body.business_date,
      reconciliation_type: body.reconciliation_type || 'production_vs_mes'
    })
    items.push(generatedItem)
    await fulfillJson(route, [generatedItem])
  })

  for (const action of ['confirm', 'ignore', 'correct']) {
    await page.route(`**/api/v1/reconciliation/items/*/${action}`, async (route) => {
      const body = route.request().postDataJSON()
      requests[action].push(body)
      const match = route.request().url().match(/\/items\/(\d+)\/[^/]+$/)
      const item = items.find((candidate) => String(candidate.id) === match?.[1])
      const nextStatus = {
        confirm: 'confirmed',
        ignore: 'ignored',
        correct: 'corrected'
      }[action]

      if (item) {
        item.status = nextStatus
        item.resolve_note = body.note
        item.resolved_by = 1
        item.resolved_at = '2026-04-23T09:00:00Z'
        item.updated_at = item.resolved_at
      }

      await fulfillJson(route, item)
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

test('reconciliation center lists details and generates differences', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  const { requests } = await setupReconciliationMocks(page)

  await page.goto('/manage/reconciliation')

  const center = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '差异核对中心' }) })
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(center.getByRole('heading', { name: '差异核对中心' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '业务日期' })).toBeVisible()
  await expect(center.getByRole('columnheader', { name: '处理状态' })).toBeVisible()
  await expect(center.getByText('XT-ZD-1')).toBeVisible()
  await expect(center.getByText('产出重量')).toBeVisible()
  await expect(center.getByText('待处理')).toBeVisible()

  await center.locator('.el-table__row', { hasText: 'XT-ZD-1' }).getByRole('button', { name: '详情' }).click()

  await expect(page).toHaveURL(/\/manage\/reconciliation\/detail\/11$/)
  await expect(page.getByRole('heading', { name: '差异详情' })).toBeVisible()
  await expect(page.getByText('生产与 MES 核对')).toBeVisible()
  await expect(page.getByText('填报端产量')).toBeVisible()
  await expect(page.getByText('外部 MES')).toBeVisible()
  await expect(page.getByText('产出重量')).toBeVisible()
  await expect(page.getByText('1175 吨')).toBeVisible()
  await expect(page.getByText('1160 吨')).toBeVisible()
  await expect(page.getByText('+15 吨')).toBeVisible()

  await page.goto('/manage/reconciliation')
  const businessDate = await page.locator('.reference-page .el-date-editor input').first().inputValue()
  await page.getByRole('button', { name: '生成差异' }).first().click()

  await expect.poll(() => requests.generate).toHaveLength(1)
  expect(requests.generate[0].business_date).toBe(businessDate)
  await expect(center.getByText('XT-ZD-2')).toBeVisible()
  await expect(center.getByText('投入重量')).toBeVisible()
})

for (const scenario of [
  {
    actionKey: 'confirm',
    actionLabel: '确认',
    rowText: '确认差异',
    statusLabel: '已确认',
    rawNote: '  班组确认 MES 口径正确  ',
    expectedNote: '班组确认 MES 口径正确'
  },
  {
    actionKey: 'ignore',
    actionLabel: '忽略',
    rowText: '忽略差异',
    statusLabel: '已忽略',
    rawNote: '能耗补录批次重复，忽略本条',
    expectedNote: '能耗补录批次重复，忽略本条'
  },
  {
    actionKey: 'correct',
    actionLabel: '修正',
    rowText: '修正差异',
    statusLabel: '已修正',
    rawNote: '按车间复核产量修正',
    expectedNote: '按车间复核产量修正'
  }
]) {
  test(`reconciliation ${scenario.actionKey} sends operator note and updates status`, async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    const { requests } = await setupReconciliationMocks(page, [
      createReconciliationItem({ id: 21, dimension_key: 'XT-ZD-1', field_name: scenario.rowText })
    ])

    await page.goto('/manage/reconciliation')

    await submitDispositionNote(page, {
      rowText: scenario.rowText,
      actionLabel: scenario.actionLabel,
      note: scenario.rawNote
    })

    await expect.poll(() => requests[scenario.actionKey]).toHaveLength(1)
    expect(requests[scenario.actionKey][0].note).toBe(scenario.expectedNote)
    await expect(page.locator('.el-table__row', { hasText: scenario.rowText }).getByText(scenario.statusLabel)).toBeVisible()
  })
}

test('fill-only operator cannot access reconciliation center', async ({ page }) => {
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
  await setupReconciliationMocks(page)

  await page.goto('/manage/reconciliation')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '差异核对中心' })).toHaveCount(0)
})
