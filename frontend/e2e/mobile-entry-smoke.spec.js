import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'

test('admin mobile entry shows the manual-first mobile fallback entry', async ({ page }) => {
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/review\/(factory|overview)/)

  const currentShiftResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/current-shift') &&
    response.request().method() === 'GET'
  )
  await page.goto('/mobile')
  await currentShiftResponse

  const currentShiftCard = page.getByTestId('mobile-current-shift')

  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(currentShiftCard).toBeVisible()
  await expect(page.getByTestId('mobile-role-bucket')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()
  await expect(page.getByRole('button', { name: '打开审阅端' })).toHaveCount(0)
  await expect(page.getByText('采集清洗小队')).toHaveCount(0)
  await expect(page.getByText('分析决策小队')).toHaveCount(0)
})
