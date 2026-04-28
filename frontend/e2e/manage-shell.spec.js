import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('ManageShell layout', () => {
  test('sidebar navigation renders and legacy review route redirects', async ({ page }) => {
    await setupReviewSessionAndMocks(page)

    await page.goto('/review/overview')

    await expect(page).toHaveURL(/\/manage\/overview$/)
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
    await expect(page.locator('.xt-manage__nav-item.router-link-active')).toContainText('总览')
  })

  test('sidebar collapses and remembers state', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()
  })
})


