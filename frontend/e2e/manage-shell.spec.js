import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('ManageShell layout', () => {
  test('sidebar navigation renders and legacy review route redirects', async ({ page }) => {
    await setupReviewSessionAndMocks(page)

    await page.goto('/review/overview')

    await expect(page).toHaveURL(/\/manage\/today$/)
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
    const activeNav = page.locator('.xt-manage__nav-item.router-link-active')
    await expect(activeNav).toContainText('日报')
    await expect(activeNav).toHaveAttribute('data-nav-title', '昨日报表')
  })

  test('sidebar collapses and remembers state', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today')

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()
    await expect(page.getByRole('button', { name: '展开侧边栏' })).toBeVisible()

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '收起侧边栏' })).toBeVisible()
  })

  test('settings drawer exposes frozen destination items', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await expect(page.getByTestId('manage-today')).toBeVisible()

    await page.locator('.xt-manage__settings-trigger').click()

    const settingsNav = page.getByRole('navigation', { name: '管理端设置' })
    await expect(settingsNav).toBeVisible()
    await expect(settingsNav.getByRole('link', { name: '系统设置' })).toHaveAttribute('href', '/manage/admin/settings')
  })

  test('mobile drawer navigation opens, routes, and closes', async ({ page }) => {
    await page.setViewportSize({ width: 860, height: 844 })
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today', { waitUntil: 'networkidle' })

    await expect(page).toHaveURL(/\/manage\/today/)
    await expect(page.getByTestId('manage-shell')).toHaveAttribute('data-nav-mode', 'drawer')
    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByRole('heading', { name: '经营总览' })).toBeVisible()

    await page.locator('.xt-manage__hamburger').click()
    const drawer = page.locator('.xt-manage__drawer')
    const mobileNav = page.getByRole('navigation', { name: '移动端管理导航' })
    await expect(mobileNav).toBeVisible()
    const liveLink = mobileNav.getByRole('link', { name: '实时调度墙' })
    await expect(liveLink).toHaveAttribute('href', '/manage/live')
    await liveLink.click({ force: true })

    await expect(page).toHaveURL(/\/manage\/live/)
    await expect(page.getByTestId('manage-live')).toBeVisible()
    await expect(drawer).toBeHidden()
  })

  test('auto rail sidebar expands when a nav link gets keyboard focus', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 800 })
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await page.mouse.move(900, 400)

    await expect(page.getByTestId('manage-shell')).toHaveAttribute('data-nav-mode', 'auto-rail')
    const sidebar = page.locator('.xt-manage__sidebar')
    const firstLabel = sidebar.locator('.xt-manage__nav-label').first()
    await expect(firstLabel).toBeHidden()

    await sidebar.locator('.xt-manage__nav-item').first().focus()

    await expect(firstLabel).toBeVisible()
  })

  test('printing hides navigation chrome including an open mobile drawer', async ({ page }) => {
    await page.setViewportSize({ width: 860, height: 844 })
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await page.locator('.xt-manage__hamburger').click()
    await expect(page.locator('.xt-manage__drawer-overlay')).toBeVisible()

    await page.emulateMedia({ media: 'print' })

    await expect(page.locator('.xt-manage__drawer-overlay')).toBeHidden()
    await expect(page.locator('.xt-manage__topbar')).toBeHidden()
    const mainMinHeight = await page.locator('.xt-manage__main').evaluate((el) => getComputedStyle(el).minHeight)
    expect(['auto', '0px']).toContain(mainMinHeight)
  })

  test('search overlay filters and routes to the selected result', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await expect(page.getByTestId('manage-today')).toBeVisible()

    await page.getByRole('button', { name: /搜索/ }).click()

    const dialog = page.getByRole('dialog', { name: '搜索' })
    await expect(dialog).toBeVisible()
    await dialog.getByPlaceholder('搜索功能').fill('异常')

    const searchItems = dialog.locator('.xt-manage__search-item')
    const alertResult = searchItems.filter({ hasText: '异常' })
    await expect(alertResult).toBeVisible()

    await alertResult.click()

    await expect(page).toHaveURL(/\/manage\/alerts$/)
    await expect(page.getByTestId('manage-alerts')).toBeVisible()
    await expect(dialog).toBeHidden()
  })
})


