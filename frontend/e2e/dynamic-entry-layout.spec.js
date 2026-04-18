import { expect, test } from '@playwright/test'

test('machine entry form shows migration-first layout with grouped secondary sections', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill('ZD-1')
  await page.getByTestId('login-password').fill('104833')
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/mobile$/)
  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/mobile\/report-advanced\//)
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-summary-strip')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toBeVisible()
  await expect(page.getByTestId('entry-core-form')).toHaveCount(0)
  await expect(page.getByTestId('entry-secondary-sections')).toHaveCount(0)
})
