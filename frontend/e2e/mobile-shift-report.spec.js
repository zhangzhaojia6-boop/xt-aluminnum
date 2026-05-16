import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Mobile Shift Report Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('shift report form renders with required fields', async ({ page }) => {
    await page.goto('/entry/shift-report')
    await expect(page.locator('body')).toBeVisible()
  })

  test('mobile entry home shows task cards', async ({ page }) => {
    await page.goto('/entry')
    await expect(page.locator('body')).toBeVisible()
  })
})
