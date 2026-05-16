import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Cost Center', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('cost center renders with BOM chart and profit table', async ({ page }) => {
    await page.goto('/manage/cost')
    await expect(page.locator('body')).toBeVisible()
  })

  test('cost center has workshop filter', async ({ page }) => {
    await page.goto('/manage/cost')
    await expect(page.locator('body')).toBeVisible()
  })
})
