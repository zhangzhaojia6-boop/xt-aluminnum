import { test, expect } from '@playwright/test'

test('login page mounts HUD theme and particle backdrop', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('[data-testid="login-hud-backdrop"]')).toBeAttached()
  await expect(page.locator('[data-testid="login-page"]')).toBeVisible()
  await expect(page.locator('[data-testid="login-brand"]')).toContainText('数据中枢')
})

test('login page does not leak forbidden product lexicon', async ({ page }) => {
  await page.goto('/login')
  const body = await page.locator('body').innerText()
  for (const forbidden of ['Cyberpunk', 'Palantir', 'Quantum', 'Sci-Fi']) {
    expect(body).not.toContain(forbidden)
  }
})

test('login page re-applies HUD theme on remount', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await page.goto('about:blank')
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
})
