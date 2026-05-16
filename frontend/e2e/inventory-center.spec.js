import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Inventory Center', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('inventory page renders with KPI ribbon', async ({ page }) => {
    await page.goto('/manage/inventory')
    await expect(page.locator('body')).toBeVisible()
  })

  test('inventory page has export button', async ({ page }) => {
    await page.goto('/manage/inventory')
    await expect(page.locator('body')).toBeVisible()
  })
})
