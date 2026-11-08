import { test, expect } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test('login page stays on the paper theme with the rolling line', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('.xt-rolling')).toBeVisible()
  await expect(page.locator('[data-testid="login-page"]')).toContainText('数据中枢')
  await expect(page.locator('[data-testid="login-brand"]')).toContainText('鑫泰铝业')
})

test('login page does not leak forbidden product lexicon', async ({ page }) => {
  await page.goto('/login')
  const body = await page.locator('body').innerText()
  for (const forbidden of ['Cyberpunk', 'Palantir', 'Quantum', 'Sci-Fi']) {
    expect(body).not.toContain(forbidden)
  }
})

test('login page has no sideways scroll on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/login')
  await expect(page.locator('[data-testid="login-submit"]')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})
