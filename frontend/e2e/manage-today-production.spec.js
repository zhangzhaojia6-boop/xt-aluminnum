import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('manage today/production content', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('today shows 5 数 + 要紧事 then drills to alerts', async ({ page }) => {
    await page.goto('/manage/today')
    await expect(page.getByTestId('manage-today')).toBeVisible()

    const kpi = page.getByTestId('manage-kpi-bar')
    for (const label of ['日产量', '比昨日', '日吨成本', '月累产量', '估算毛利']) {
      await expect(kpi.getByText(label, { exact: true }).first()).toBeVisible()
    }

    const reconLink = page.getByRole('link', { name: /对账未结/ })
    await expect(reconLink).toBeVisible()
    await reconLink.click()
    await expect(page).toHaveURL(/\/manage\/alerts.*surface=reconciliation/)
  })

  test('production shows 5 数 + 车间排名表', async ({ page }) => {
    await page.goto('/manage/production')
    await expect(page.getByTestId('manage-production')).toBeVisible()

    const kpi = page.getByTestId('manage-kpi-bar')
    for (const label of ['已产', '比昨日', '估算毛利', '合同缺口', '日吨能耗']) {
      await expect(kpi.getByText(label, { exact: true }).first()).toBeVisible()
    }

    const rows = page.locator('[data-testid="manage-production-table"] tbody tr')
    await expect(rows).toHaveCount(2)
    await expect(rows.nth(0)).toContainText('挤压车间')
    await expect(rows.nth(1)).toContainText('熔铸车间')

    await expect(page.getByText('月均', { exact: false }).first()).toBeVisible()
  })

  test('neither tab uses banned phrasing', async ({ page }) => {
    await page.goto('/manage/today')
    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByText('达成率')).toHaveCount(0)
    await expect(page.getByText('班次进度')).toHaveCount(0)

    await page.goto('/manage/production')
    await expect(page.getByTestId('manage-production')).toBeVisible()
    await expect(page.getByText('达成率')).toHaveCount(0)
    await expect(page.getByText('班次进度')).toHaveCount(0)
  })
})
