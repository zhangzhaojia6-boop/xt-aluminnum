import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Workshop Director Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('renders workshop dashboard page', async ({ page }) => {
    await page.goto('/manage/workshop-dashboard')
    await expect(page.getByTestId('workshop-dashboard')).toBeVisible()
  })

  test('shows workshop-level metrics', async ({ page }) => {
    await page.goto('/manage/workshop-dashboard')
    await expect(page.getByTestId('workshop-dashboard')).toBeVisible()
    await expect(page.getByText('机列填报明细')).toBeVisible()
    await expect(page.getByText('电工填报明细')).toBeVisible()
  })
})
