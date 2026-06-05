import { test, expect } from '@playwright/test'

import {
  setupReviewSessionAndMocks,
  mockQualityIssues,
  mockReconciliationItems,
  mockQualityFailure
} from './helpers/review-mocks'

test.describe('manage alerts timeline (Phase C-1)', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await mockQualityIssues(page, [
      {
        id: 'q1',
        issue_type: 'invalid_value',
        source_type: 'production',
        dimension_key: 'yield_rate',
        field_name: 'yield_rate',
        issue_level: 'warning',
        issue_desc: '抽检不合格',
        status: 'open',
        business_date: '2026-05-19',
        created_at: '2026-05-19T11:00:00',
        updated_at: '2026-05-19T11:00:00'
      }
    ])
    await mockReconciliationItems(page, [
      {
        id: 'rc1',
        reconciliation_type: 'production_vs_mes',
        dimension_key: '过磅重量',
        source_a_value: 100,
        source_b_value: 97,
        diff_value: 3,
        status: 'open',
        created_at: '2026-05-19T09:50:00'
      }
    ])
  })

  test('reconciliation route activates chip and filters the list', async ({ page }) => {
    await page.goto('/manage/alerts?domain=reconciliation')
    await expect(page).toHaveURL(/\/manage\/alerts\?domain=reconciliation/)
    await expect(page.locator('.xt-domain-chip', { hasText: /对账/ })).toHaveClass(/is-active/)
    await expect(page.locator('.xt-event-card', { hasText: /生产与 MES 核对/ })).toBeVisible()
    await expect(page.getByText('抽检不合格')).toHaveCount(0)
  })

  test('date switcher refreshes the list', async ({ page }) => {
    await page.goto('/manage/alerts')
    await expect(page.locator('.xt-event-timeline__summary')).toContainText(/共 \d+ 件|当日无异常/)
    await page.getByRole('button', { name: '前一天' }).click()
    await expect(page.locator('.xt-event-timeline__summary')).toBeVisible()
  })

  test('multi-select chips filter the list', async ({ page }) => {
    await page.goto('/manage/alerts')
    await expect(page).toHaveURL(/\/manage\/alerts$/)
    const domainGroup = page.getByRole('group', { name: '异常域过滤' })
    const productionChip = domainGroup.getByRole('button', { name: /生产 \d/ })

    await productionChip.click()
    await expect(page).toHaveURL(/domain=production/)
    await expect(productionChip).toHaveClass(/is-active/)

    const reconciliationChip = domainGroup.getByRole('button', { name: /对账 \d/ })
    await expect(reconciliationChip).toBeVisible()
    await reconciliationChip.click()
    await expect(reconciliationChip).toHaveClass(/is-active/)
    await expect(page).toHaveURL(/domain=production,reconciliation|domain=reconciliation,production/)
    await expect(page.getByText('抽检不合格')).toHaveCount(0)
    await expect(page.locator('.xt-event-card', { hasText: /挤压车间 早班 迟报/ })).toBeVisible()
    await expect(page.locator('.xt-event-card', { hasText: /生产与 MES 核对/ })).toBeVisible()
  })

  test('quality 500 → fallback card injected', async ({ page }) => {
    await mockQualityFailure(page)
    await page.goto('/manage/alerts')
    await expect(page.locator('.xt-event-card', { hasText: '加载失败，点击查看异常页' })).toBeVisible()
  })

  test('production card click keeps the anomaly alert surface', async ({ page }) => {
    await page.goto('/manage/alerts')
    await page.locator('.xt-event-card', { hasText: /挤压车间 早班 迟报/ }).click()
    await expect(page).toHaveURL(/\/manage\/alerts\?surface=anomaly/)
  })

  test('legacy anomalies path lands on production alerts instead of the yesterday report', async ({ page }) => {
    await page.goto('/manage/anomalies')
    await expect(page).toHaveURL(/\/manage\/alerts\?domain=production/)
    await expect(page.getByTestId('manage-alerts')).toBeVisible()
    await expect(page.getByRole('heading', { name: '异常', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: '昨日总览' })).toHaveCount(0)
  })
})
