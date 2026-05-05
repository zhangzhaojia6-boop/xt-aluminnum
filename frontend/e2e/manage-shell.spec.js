import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('ManageShell layout', () => {
  test('sidebar navigation renders and legacy review route redirects', async ({ page }) => {
    await setupReviewSessionAndMocks(page)

    await page.goto('/review/overview')

    await expect(page).toHaveURL(/\/manage\/overview$/)
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
    await expect(page.locator('.xt-manage__nav-item.router-link-active')).toContainText('总览')
  })

  test('sidebar collapses and remembers state', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()
    await expect.poll(() => page.evaluate(() => localStorage.getItem('xt-sidebar-collapsed'))).toBe('true')

    await page.reload()

    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()

    await page.locator('.xt-manage__collapse-btn').click()

    await expect(page.locator('.xt-manage--collapsed')).toHaveCount(0)
    await expect.poll(() => page.evaluate(() => localStorage.getItem('xt-sidebar-collapsed'))).toBe('false')
  })

  test('factory cost benefit surface is visible from the management navigation', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')

    await expect(page.locator('.xt-manage__nav-item', { hasText: '经营效益' })).toBeVisible()
    await page.locator('.xt-manage__nav-item', { hasText: '经营效益' }).click()
    await expect(page).toHaveURL(/\/manage\/factory\/cost$/)
    await expect(page.getByRole('heading', { name: '经营效益' })).toBeVisible()
    await expect(page.getByText('经营估算')).toBeVisible()
    await expect(page.getByText('毛差估算')).toBeVisible()
  })

  test('mobile drawer navigation opens, routes, and closes', async ({ page }) => {
    await page.setViewportSize({ width: 1000, height: 844 })
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')

    await page.getByRole('button', { name: '打开导航' }).click()

    const drawer = page.locator('.xt-manage__drawer')
    await expect(drawer).toBeVisible()
    await drawer.getByRole('link', { name: '经营效益 估算' }).click()

    await expect(page).toHaveURL(/\/manage\/factory\/cost/)
    await expect(page.getByRole('heading', { name: '经营效益' })).toBeVisible()
    await expect(drawer).toBeHidden()
  })

  test('search overlay filters and routes to the selected result', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')

    await page.keyboard.press('Control+K')

    const dialog = page.getByRole('dialog', { name: '搜索' })
    await expect(dialog).toBeVisible()
    await dialog.getByPlaceholder('搜索功能').fill('质量')

    const qualityResult = dialog.locator('.xt-manage__search-item', { hasText: '质量' })
    await expect(qualityResult).toBeVisible()
    await expect(dialog.locator('.xt-manage__search-item', { hasText: '经营效益' })).toHaveCount(0)

    await qualityResult.click()

    await expect(page).toHaveURL(/\/manage\/quality$/)
    await expect(page.getByRole('heading', { name: '质量与告警中心' })).toBeVisible()
    await expect(dialog).toHaveCount(0)
  })
})


