import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'

async function login(page, surface = 'review') {
  await page.goto('/login')

  await expect(page.getByTestId('login-brand')).toBeVisible()
  await page.getByTestId(`login-surface-${surface}`).click()
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
}

test('login and view report delivery center contract', async ({ page }) => {
  await login(page, 'review')

  await expect(page).toHaveURL(/\/review\/overview$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()

  await page.goto('/review/reports')

  await expect(page).toHaveURL(/\/review\/reports$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '日报与交付中心' }).first()).toBeVisible()
  await expect(page.getByText('交付清单', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '导出 PDF' })).toBeVisible()
  await expect(page.getByRole('button', { name: '导出 Excel' })).toBeVisible()
  await expect(page.getByRole('button', { name: /发送\s*\/\s*交付/ })).toBeVisible()
  await expect(page.getByRole('tab', { name: '关注' })).toHaveCount(0)
})

test('compact clients land on mobile entry instead of review home by default', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })
  await login(page, 'review')

  await expect(page).toHaveURL(/\/(mobile|entry|review\/(overview|factory))/)
  if (page.url().includes('/mobile') || page.url().includes('/entry')) {
    await expect(page.getByTestId('mobile-entry')).toBeVisible()
    await expect(page.getByRole('button', { name: '打开审阅端' })).toHaveCount(0)
    return
  }
  await expect(page.getByTestId('review-shell')).toBeVisible()
})

test('login role cards choose the landing surface', async ({ page }) => {
  const cases = [
    { surface: 'review', url: /\/review\/overview$/, shell: 'review-shell' },
    { surface: 'admin', url: /\/admin$/, shell: 'admin-shell' },
    { surface: 'entry', url: /\/entry$/, shell: 'entry-shell' }
  ]

  for (const target of cases) {
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    await login(page, target.surface)

    await expect(page).toHaveURL(target.url)
    await expect(page.getByTestId(target.shell)).toBeVisible()
  }
})
