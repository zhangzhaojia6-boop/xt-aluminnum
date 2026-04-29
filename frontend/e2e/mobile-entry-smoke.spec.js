import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'

test('admin mobile entry shows the manual-first mobile fallback entry', async ({ page }) => {
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/dashboard\/factory/, { timeout: 15000 })

  await page.goto('/entry')

  const currentShiftCard = page.getByTestId('mobile-current-shift')

  await expect(page).toHaveURL(/\/mobile/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(currentShiftCard).toBeVisible()
  await expect(page.getByTestId('mobile-role-bucket')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()
  await expect(currentShiftCard).toContainText('录入方式')
})
