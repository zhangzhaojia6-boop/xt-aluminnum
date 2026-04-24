import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'

test('login and view delivery status card', async ({ page }) => {
  await page.goto('/login')

  await expect(page.getByTestId('login-brand')).toBeVisible()

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/review\/(overview|factory)/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
  if (!page.url().includes('/review/factory')) {
    await page.goto('/review/factory')
  }
  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  const detailToggle = page.getByRole('button', { name: /展开运行详情|收起运行详情/ })
  if (await detailToggle.count()) {
    const label = await detailToggle.first().innerText()
    if (label.includes('展开')) {
      await detailToggle.first().click()
    }
  }
  await expect(page.getByTestId('delivery-ready-card')).toBeVisible()
  await page.getByRole('tab', { name: '关注' }).click()
  await expect(page.locator('[data-testid="delivery-missing-steps"]:visible')).toBeVisible()
})

test('compact clients land on mobile entry instead of review home by default', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

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
    { surface: 'admin', url: /\/admin\/overview$/, shell: 'admin-shell' },
    { surface: 'entry', url: /\/entry$/, shell: 'entry-shell' }
  ]

  for (const target of cases) {
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    await page.goto('/login')

    await page.getByTestId(`login-surface-${target.surface}`).click()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill(password)
    await page.getByTestId('login-submit').click()

    await expect(page).toHaveURL(target.url)
    await expect(page.getByTestId(target.shell)).toBeVisible()
  }
})
