import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'

test('production compose serves login and authenticated manage route', async ({ page }) => {
  await page.goto('/login')

  await expect(page.getByTestId('login-brand')).toBeVisible()
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).not.toHaveURL(/\/login(?:\?|$)/)

  await page.goto('/manage/reports')

  await expect(page).toHaveURL(/\/manage\/reports$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '日报与交付中心' }).first()).toBeVisible()
})
