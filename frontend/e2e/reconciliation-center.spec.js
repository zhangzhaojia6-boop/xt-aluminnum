import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'
import { setupStoredFillOnlySession } from './helpers/fill-only-session'

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

// 差异核对中心列表、生成差异、确认、忽略和更正已随改版并入异常页（旧地址见 review-runtime.spec.js），这里只保留仍在的详情页
test('reconciliation detail page shows the difference', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await setupReconciliationMocks(page)

  await page.goto('/manage/reconciliation/detail/11')

  await expect(page.getByRole('heading', { name: '差异详情' })).toBeVisible()
  await expect(page.getByText('生产与 MES 核对')).toBeVisible()
  await expect(page.getByText('填报端产量')).toBeVisible()
  await expect(page.getByText('外部 MES')).toBeVisible()
  await expect(page.getByText('产出重量')).toBeVisible()
  await expect(page.getByText('1175 吨')).toBeVisible()
  await expect(page.getByText('1160 吨')).toBeVisible()
  await expect(page.getByText('+15 吨')).toBeVisible()
})

test('fill-only operator cannot access reconciliation center', async ({ page }) => {
  await setupStoredFillOnlySession(page)
  await setupReconciliationMocks(page)

  await page.goto('/manage/reconciliation')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '差异核对中心' })).toHaveCount(0)
})
