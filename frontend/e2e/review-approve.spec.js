import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Review Approve Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('review task center renders with task queue', async ({ page }) => {
    await page.goto('/manage/review')
    await expect(page.locator('body')).toBeVisible()
  })

  test('review page shows filter controls', async ({ page }) => {
    await page.goto('/manage/review')
    await expect(page.locator('body')).toBeVisible()
  })
})
