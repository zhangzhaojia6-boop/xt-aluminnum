import { test, expect } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

test('manage shell opts into HUD when preference is set', async ({ page, context }) => {
  // 登录用户的主题以后端偏好为准，进页面时会用它覆盖本地缓存
  await page.route('**/api/v1/user/preferences', (route) => route.fulfill({ json: { theme: 'hud' } }))
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/today')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('[data-testid="manage-shell"]')).toBeVisible()
})

test('manage shell is dark by default even without a saved preference', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.removeItem('xt-theme-preference'))
  await page.goto('/manage/today')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('html')).toHaveClass(/(^|\s)dark(\s|$)/)
})

test('emergency switch brings the manage shell back to light', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-force-light', '1'))
  await page.goto('/manage/today')
  await expect(page.getByTestId('manage-today')).toBeVisible()
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
})

test('manage shell always renders 数据中枢 brand text', async ({ page, context }) => {
  await context.addInitScript(() => localStorage.setItem('xt-theme-preference', 'hud'))
  await page.goto('/manage/today')
  await expect(page.locator('.xt-manage__brand')).toContainText('数据中枢')
})
