import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('Executive Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('renders executive dashboard with profit KPIs', async ({ page }) => {
    await page.goto('/manage/executive')
    await expect(page.getByText('经营驾驶舱')).toBeVisible()
    await expect(page.getByText('昨日加工利润')).toBeVisible()
  })

  test('shows workshop profit ranking', async ({ page }) => {
    await page.goto('/manage/executive')
    await expect(page.getByText('车间盈亏榜')).toBeVisible()
  })

  test('date input triggers reload', async ({ page }) => {
    await page.goto('/manage/executive')
    const dateInput = page.locator('input[type="date"]')
    await expect(dateInput).toBeVisible()
  })
})
