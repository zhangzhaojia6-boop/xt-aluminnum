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
      { id: 'q1', occurred_at: '2026-05-19T11:00:00', summary: '抽检不合格' }
    ])
    await mockReconciliationItems(page, [
      { id: 'rc1', occurred_at: '2026-05-19T09:50:00', summary: '3 笔过磅与系统差异' }
    ])
  })

  test('today key event 对账 → /manage/alerts?domain=reconciliation, chip active, list filtered', async ({ page }) => {
    await page.goto('/manage/today')
    await page.getByRole('link', { name: /对账未结/ }).click()
    await expect(page).toHaveURL(/\/manage\/alerts\?domain=reconciliation/)
    await expect(page.locator('.xt-domain-chip', { hasText: /对账/ })).toHaveClass(/is-active/)
    await expect(page.getByText('3 笔过磅与系统差异')).toBeVisible()
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
    await page.getByRole('button', { name: /生产 \d/ }).click()
    await page.getByRole('button', { name: /对账 \d/ }).click()
    await expect(page.getByText('抽检不合格')).toHaveCount(0)
    await expect(page.getByText('一车间早班产量异常 -2.4%')).toBeVisible()
    await expect(page.getByText('3 笔过磅与系统差异')).toBeVisible()
  })

  test('quality 500 → fallback card injected', async ({ page }) => {
    await mockQualityFailure(page)
    await page.goto('/manage/alerts')
    await expect(page.getByText('加载失败，点击查看老页')).toBeVisible()
  })

  test('production card click navigates to legacy surface', async ({ page }) => {
    await page.goto('/manage/alerts')
    await page.getByText('一车间早班产量异常 -2.4%').click()
    await expect(page).toHaveURL(/\/manage\/alerts\/legacy\?surface=anomaly/)
  })
})
