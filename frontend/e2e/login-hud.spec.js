import { test, expect } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test('login page is dark with the company photo on wide screens', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const photo = page.waitForResponse((response) => response.url().endsWith('/media/login-coils.webp'))
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.getByTestId('login-photo')).toBeVisible()
  expect((await photo).status()).toBe(200)
  await expect(page.locator('.xt-rolling')).toBeHidden()
  await expect(page.locator('[data-testid="login-page"]')).toContainText('数据中枢')
  await expect(page.locator('[data-testid="login-brand"]')).toContainText('鑫泰铝业')
})

test('phones keep the rolling line and never download the photo', async ({ page }) => {
  const photoRequests = []
  page.on('request', (request) => {
    if (request.url().includes('/media/')) photoRequests.push(request.url())
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await expect(page.locator('.xt-rolling')).toBeVisible()
  await expect(page.getByTestId('login-photo')).toBeHidden()
  await page.waitForLoadState('networkidle')
  expect(photoRequests).toEqual([])
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
