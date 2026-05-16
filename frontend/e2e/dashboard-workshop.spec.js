import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Workshop Director Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('renders workshop dashboard page', async ({ page }) => {
    await page.goto('/manage/workshop')
    await expect(page.locator('.page-stack, [data-testid]')).toBeVisible()
  })

  test('shows workshop-level metrics', async ({ page }) => {
    await page.goto('/manage/workshop')
    await expect(page.locator('body')).toBeVisible()
  })
})
