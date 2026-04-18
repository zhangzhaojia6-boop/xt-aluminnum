import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'

test('login and view delivery status card', async ({ page }) => {
  await page.goto('/login')

  await expect(page.getByTestId('login-brand')).toBeVisible()

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/dashboard\/factory/)
  await expect(page.getByTestId('app-shell')).toBeVisible()
  await expect(page.getByTestId('desktop-brand')).toBeVisible()
  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByTestId('delivery-ready-card')).toBeVisible()
  await expect(page.getByTestId('delivery-missing-steps')).toBeVisible()
})
