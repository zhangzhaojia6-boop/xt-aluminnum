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

  test('shows placeholders instead of dashes or a made-up exception count while loading', async ({ page }) => {
    await page.route('**/api/v1/dashboard/workshop-director**', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 3000))
      await route.fallback()
    })
    await page.goto('/manage/workshop-dashboard')
    await expect(page.getByTestId('workshop-dashboard')).toBeVisible()
    await expect(page.getByTestId('kpi-loading').first()).toBeVisible()
    await expect(page.locator('.workshop-board__kpi strong', { hasText: /^-$/ })).toHaveCount(0)
    await expect(page.locator('.workshop-board__exception strong')).toHaveCount(0)
    await expect(page.getByTestId('kpi-loading')).toHaveCount(0, { timeout: 10000 })
    await expect(page.locator('.workshop-board__exception strong')).toHaveCount(4)
  })
})
