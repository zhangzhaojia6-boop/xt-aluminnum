import { expect, test } from '@playwright/test'
import { firstEnv, skipWithoutCredentials } from './helpers/credentials'
import { clearAuthStorage } from './helpers/mock-login'

const username = firstEnv('PLAYWRIGHT_USERNAME', 'INIT_ADMIN_USERNAME')
const password = firstEnv('PLAYWRIGHT_PASSWORD', 'INIT_ADMIN_PASSWORD')

test('production compose serves login and authenticated manage route', async ({ page }) => {
  skipWithoutCredentials([
    ['PLAYWRIGHT_USERNAME or INIT_ADMIN_USERNAME', username],
    ['PLAYWRIGHT_PASSWORD or INIT_ADMIN_PASSWORD', password]
  ])

  await clearAuthStorage(page)
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
