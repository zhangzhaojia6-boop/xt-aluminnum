import { test, expect } from '@playwright/test'

test('manage shell opts into HUD when preference is set', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/today')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('[data-testid="manage-shell"]')).toBeVisible()
})

test('manage shell stays in default light theme without preference', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.removeItem('xt-theme-preference'))
  await page.goto('/manage/today')
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
})

test('manage shell always renders 数据中枢 brand text', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/today')
  await expect(page.locator('.xt-manage__brand')).toContainText('数据中枢')
})
