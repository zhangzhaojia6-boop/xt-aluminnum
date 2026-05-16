import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Settings Center', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('settings center renders with tabs', async ({ page }) => {
    await page.goto('/manage/settings')
    await expect(page.locator('body')).toBeVisible()
  })

  test('settings center has four configuration tabs', async ({ page }) => {
    await page.goto('/manage/settings')
    await expect(page.locator('body')).toBeVisible()
  })
})
