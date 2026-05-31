import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('ManageShell layout', () => {
  test('sidebar navigation renders and legacy review route redirects', async ({ page }) => {
    await setupReviewSessionAndMocks(page)

    await page.goto('/review/overview')

    await expect(page).toHaveURL(/\/manage\/today$/)
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
    await expect(page.locator('.xt-manage__nav-item.router-link-active')).toContainText('昨日日报')
  })

  test('sidebar collapses and remembers state', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today')

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()
    await expect.poll(() => page.evaluate(() => localStorage.getItem('xt-sidebar-collapsed'))).toBe('true')

    await page.reload()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toHaveCount(0)
    await expect.poll(() => page.evaluate(() => localStorage.getItem('xt-sidebar-collapsed'))).toBe('false')
  })

  test('settings drawer exposes frozen destination items', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today')

    await page.getByRole('button', { name: '设置' }).click()

    await expect(page.getByText('杂项 (冻结)')).toBeVisible()
    await expect(page.getByRole('link', { name: /库存去向/ })).toBeVisible()
  })

  test('mobile drawer navigation opens, routes, and closes', async ({ page }) => {
    await page.setViewportSize({ width: 860, height: 844 })
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today?desktop=1')

    await expect(page).toHaveURL(/\/manage\/today/)
    await expect(page.getByRole('heading', { name: '昨日总览' })).toBeVisible()

    await page.getByRole('button', { name: '打开导航' }).click()
    const drawer = page.locator('.xt-manage__drawer')
    await expect(page.getByRole('navigation', { name: '移动端管理导航' })).toBeVisible()
    await drawer.getByRole('link', { name: '生产', exact: true }).click()

    await expect(page).toHaveURL(/\/manage\/production/)
    await expect(page.getByTestId('manage-production')).toBeVisible()
    await expect(drawer).toBeHidden()
  })

  test('search overlay filters and routes to the selected result', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/today')

    await page.getByRole('button', { name: '搜索 Ctrl K' }).click()

    const dialog = page.locator('.xt-search-overlay')
    await expect(dialog).toBeVisible()
    await dialog.getByPlaceholder('搜索功能').fill('异常')

    const alertResult = dialog.locator('.xt-manage__search-item', { hasText: '异常' })
    await expect(alertResult).toBeVisible()
    await expect(dialog.locator('.xt-manage__search-item')).toHaveCount(1)

    await alertResult.click()

    await expect(page).toHaveURL(/\/manage\/alerts$/)
    await expect(page.getByTestId('manage-alerts')).toBeVisible()
    await expect(dialog).toBeHidden()
  })
})


