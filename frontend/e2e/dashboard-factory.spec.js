import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

// 厂长驾驶舱已在 d3399609 下线；旧书签按路由表落到生产分析
test.describe('retired factory director dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  for (const path of ['/dashboard/factory', '/factory']) {
    test(`${path} lands on production analysis`, async ({ page }) => {
      await page.goto(path)
      await expect(page).toHaveURL(/\/manage\/production$/)
      await expect(page.getByTestId('manage-production')).toBeVisible()
    })
  }
})
