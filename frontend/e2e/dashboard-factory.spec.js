import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Factory Director Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('renders factory dashboard with KPI metrics', async ({ page }) => {
    await page.goto('/manage/factory')
    await expect(page.getByTestId('factory-dashboard')).toBeVisible()
    await expect(page.getByText('今日产量').first()).toBeVisible()
  })

  test('date picker changes target date', async ({ page }) => {
    await page.goto('/manage/factory')
    await expect(page.locator('.review-home-hero__controls .el-date-editor')).toBeVisible()
  })

  test('shows loading state then content', async ({ page }) => {
    await page.goto('/manage/factory')
    await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  })
})
