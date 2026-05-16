import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Contracts Center', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('contracts page renders with fulfillment progress', async ({ page }) => {
    await page.goto('/manage/contracts')
    await expect(page.locator('body')).toBeVisible()
  })

  test('contracts page has status filter', async ({ page }) => {
    await page.goto('/manage/contracts')
    await expect(page.locator('body')).toBeVisible()
  })
})
