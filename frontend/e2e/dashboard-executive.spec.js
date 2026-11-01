import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

// 经营驾驶舱已在 d3399609 下线并入经营总览；旧书签仍要落到经营总览
test.describe('retired executive dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  for (const path of ['/dashboard/executive', '/manage/executive']) {
    test(`${path} lands on the business overview`, async ({ page }) => {
      await page.goto(path)
      await expect(page).toHaveURL(/\/manage\/today$/)
      await expect(page.getByRole('heading', { name: '经营总览' })).toBeVisible()
    })
  }
})
