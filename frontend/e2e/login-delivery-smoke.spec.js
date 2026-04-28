import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'

async function login(page) {
  await page.goto('/login')

  await expect(page.getByTestId('login-brand')).toBeVisible()
  await expect(page.getByTestId('login-surface-entry')).toBeVisible()
  await expect(page.getByTestId('login-surface-review')).toBeVisible()
  await expect(page.getByTestId('login-surface-admin')).toBeVisible()
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
}

test('login and view report delivery center contract', async ({ page }) => {
  await login(page)

  await expect(page).toHaveURL(/\/(manage\/admin|entry|manage\/overview)$/)

  await page.goto('/manage/reports')

  await expect(page).toHaveURL(/\/manage\/reports$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '日报与交付中心' }).first()).toBeVisible()
  await expect(page.getByText('交付清单', { exact: true })).toBeVisible()
  await expect(page.locator('.el-form-item__label', { hasText: '报告类型' })).toBeVisible()
  await expect(page.locator('.el-form-item__label', { hasText: '当前状态' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '关键摘要' })).toBeVisible()
  await expect(page.getByText('暂无数据')).toBeVisible()
  await expect(page.getByRole('tab', { name: '关注' })).toHaveCount(0)
})

test('compact clients land on mobile entry instead of review home by default', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })
  await login(page)

  await expect(page).toHaveURL(/\/(manage\/admin|mobile|entry|manage\/(overview|factory))/)
  if (page.url().includes('/manage/admin')) {
    await expect(page.getByTestId('manage-shell')).toBeVisible()
    return
  }
  if (page.url().includes('/mobile') || page.url().includes('/entry')) {
    await expect(page.getByTestId('mobile-entry')).toBeVisible()
    await expect(page.getByRole('button', { name: '打开审阅端' })).toHaveCount(0)
    return
  }
  await expect(page.getByTestId('manage-shell')).toBeVisible()
})

test('stored admin session is routed to the permission default without role choice', async ({ page }) => {
  await setupReviewSessionAndMocks(page)

  await page.goto('/login')

  await expect(page).toHaveURL(/\/manage\/admin$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
})

test('stored fill-only session is routed to entry without role choice', async ({ page }) => {
  await setupReviewSessionAndMocks(page, {
    token: 'playwright-fill-token',
    user: {
      id: 2,
      username: 'operator',
      name: 'Playwright Operator',
      role: 'operator',
      is_mobile_user: true,
      is_reviewer: false,
      is_manager: false,
      data_scope_type: 'self_team',
      assigned_shift_ids: []
    }
  })

  await page.goto('/login')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
})
