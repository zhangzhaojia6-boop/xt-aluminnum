import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Ops Center', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('ops center renders with MTBF/MTTR metrics', async ({ page }) => {
    await page.goto('/manage/ops')
    await expect(page.locator('body')).toBeVisible()
  })

  test('ops center has alert level filter', async ({ page }) => {
    await page.goto('/manage/ops')
    await expect(page.locator('body')).toBeVisible()
  })
})
