import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('owner three-tab skeleton', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('today tab renders with the three owner navigation groups', async ({ page }) => {
    await page.goto('/manage/today')

    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByRole('heading', { name: '今日' })).toBeVisible()
    await expect(page.locator('.xt-manage__sidebar .xt-manage__nav-group-label')).toHaveText(['今日', '生产', '异常'])
  })

  test('navigates the three owner tabs without 404', async ({ page }) => {
    await page.goto('/manage/today')

    await page.getByRole('link', { name: '生产', exact: true }).click()
    await expect(page).toHaveURL(/\/manage\/production$/)
    await expect(page.getByTestId('manage-production')).toBeVisible()

    await page.getByRole('link', { name: '异常', exact: true }).click()
    await expect(page).toHaveURL(/\/manage\/alerts$/)
    await expect(page.getByTestId('manage-alerts')).toBeVisible()

    await page.getByRole('link', { name: '今日', exact: true }).click()
    await expect(page).toHaveURL(/\/manage\/today$/)
    await expect(page.getByTestId('manage-today')).toBeVisible()
  })

  test('legacy management paths redirect into the owner skeleton', async ({ page }) => {
    await page.goto('/manage/today')
    await expect(page).toHaveURL(/\/manage\/today$/)

    await page.goto('/manage/factory')
    await expect(page).toHaveURL(/\/manage\/production$/)

    await page.goto('/manage/quality')
    await expect(page).toHaveURL(/\/manage\/alerts(?:\?domain=quality)?$/)
  })

  test('settings drawer exposes frozen destinations and routes to the page', async ({ page }) => {
    await page.goto('/manage/today')

    await page.getByRole('button', { name: '设置' }).click()
    await expect(page.getByText('杂项 (冻结)')).toBeVisible()

    const destinationLink = page.getByRole('link', { name: /库存去向/ })
    await expect(destinationLink).toBeVisible()
    await destinationLink.click()

    await expect(page).toHaveURL(/\/manage\/factory\/destinations$/)
  })
})
