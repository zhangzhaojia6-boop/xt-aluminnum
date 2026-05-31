import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

async function expectNoHorizontalOverflow(page) {
  await expect.poll(async () => {
    try {
      return await page.evaluate(() => {
        const root = document.scrollingElement || document.documentElement
        return Math.max(root.scrollWidth, document.body.scrollWidth) - window.innerWidth
      })
    } catch {
      return Number.POSITIVE_INFINITY
    }
  }).toBeLessThanOrEqual(2)
}

async function expectManageChrome(page) {
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  if ((page.viewportSize()?.width || 0) <= 900) {
    await expect(page.locator('.xt-manage__hamburger')).toBeVisible()
  } else {
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
  }
  await expectNoHorizontalOverflow(page)
}

test('manage shell keeps the production surface readable across desktop tablet and mobile override', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/manage/production')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()

  await page.setViewportSize({ width: 900, height: 1180 })
  await page.goto('/manage/production?desktop=1')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()

  await page.setViewportSize({ width: 430, height: 932 })
  await page.goto('/manage/production?desktop=1')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()
})

test('manage shell keeps current core centers readable on tablet and mobile widths', async ({ page }) => {
  const centers = [
    { path: '/manage/today', testId: 'manage-today' },
    { path: '/manage/production', testId: 'manage-production' },
    { path: '/manage/fill-details', testId: 'manage-fill-details' },
    { path: '/manage/admin/settings', testId: 'system-settings-page' }
  ]

  for (const width of [1100, 430]) {
    await page.setViewportSize({ width, height: width === 1100 ? 900 : 932 })

    for (const center of centers) {
      await page.goto(width <= 900 ? `${center.path}?desktop=1` : center.path)
      await expectManageChrome(page)
      await expect(page.getByTestId(center.testId)).toBeVisible()
    }
  }
})

test('production center exposes current production board and summary sections', async ({ page }) => {
  await page.goto('/manage/production')

  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()
  await expect(page.getByRole('heading', { name: '生产', exact: true })).toBeVisible()
  await expect(page.getByText('车间产量排名')).toBeVisible()
  await expect(page.getByText('生产摘要')).toBeVisible()
})
