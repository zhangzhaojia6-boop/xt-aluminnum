import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test('login is dark from the very first paint, before the app boots', async ({ page }) => {
  await page.route(/\/src\/main\.js|\/assets\/index-.*\.js/, (route) => route.abort())
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  const background = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor)
  expect(background).toBe('rgb(6, 13, 24)')
})

test('phone fill-in pages stay light even with a saved dark preference', async ({ page }) => {
  const token = 'playwright-fill-token'
  const user = { id: 2, username: 'operator', name: '填报工', role: 'operator', is_mobile_user: true, is_reviewer: false, is_manager: false, data_scope_type: 'self_team', assigned_shift_ids: [] }
  await setupReviewSessionAndMocks(page, { token, user, skipLogin: true })
  await page.addInitScript(({ token, user }) => {
    for (const store of [localStorage, sessionStorage]) {
      store.setItem('aluminum_bypass_token', token)
      store.setItem('aluminum_bypass_user', JSON.stringify(user))
    }
    localStorage.setItem('xt-theme-preference', 'hud')
  }, { token, user })

  await page.goto('/entry')
  await expect(page).toHaveURL(/\/entry/)
  await expect(page.locator('html')).not.toHaveAttribute('data-xt-theme', 'hud')
  await expect(page.locator('html')).not.toHaveClass(/(^|\s)dark(\s|$)/)
})

test('Element Plus popups follow the dark palette', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/manage/admin/users')
  await page.getByTestId('admin-users-center').locator('.el-select').first().click()
  const popper = page.locator('.el-select__popper:visible, .el-select-dropdown:visible').first()
  await expect(popper).toBeVisible()
  const background = await popper.evaluate((el) => getComputedStyle(el).backgroundColor)
  expect(background).toBe('rgb(17, 30, 51)')
})

test('printing the dark manage pages gives white paper and dark text', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.goto('/manage/today')
  await expect(page.locator('html')).toHaveAttribute('data-xt-theme', 'hud')
  await page.emulateMedia({ media: 'print' })
  const colors = await page.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor,
    text: getComputedStyle(document.body).color
  }))
  expect(colors).toEqual({ bg: 'rgb(255, 255, 255)', text: 'rgb(17, 24, 39)' })
})
