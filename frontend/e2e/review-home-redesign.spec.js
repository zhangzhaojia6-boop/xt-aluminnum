import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

async function expectFactoryCenter(page) {
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  if ((page.viewportSize()?.width || 0) > 1180) {
    await expect(page.locator('.xt-manage__brand')).toContainText('鑫')
  } else {
    await expect(page.locator('.xt-manage__hamburger')).toBeVisible()
  }
  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂作业看板' })).toBeVisible()
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
  await expectNoHorizontalOverflow(page)
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement
    return {
      windowWidth: window.innerWidth,
      documentWidth: root.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }
  })
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.windowWidth + 2)
  expect(overflow.bodyWidth).toBeLessThanOrEqual(overflow.windowWidth + 2)
}

test('manage shell keeps the factory center readable across desktop tablet and mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/manage/factory')
  await expectFactoryCenter(page)

  await page.setViewportSize({ width: 900, height: 1180 })
  await expectFactoryCenter(page)

  await page.setViewportSize({ width: 430, height: 932 })
  await expectFactoryCenter(page)
})

test('manage shell keeps dense centers readable on tablet and mobile widths', async ({ page }) => {
  const centers = [
    { path: '/manage/overview', testId: 'review-overview-center' },
    { path: '/manage/factory', testId: 'factory-dashboard' },
    { path: '/manage/master', testId: 'admin-master-center' },
    { path: '/manage/ai', selector: '.ai-workstation' }
  ]

  for (const width of [1100, 430]) {
    await page.setViewportSize({ width, height: width === 1100 ? 900 : 932 })

    for (const center of centers) {
      await page.goto(width <= 900 ? `${center.path}?desktop=1` : center.path)
      await expect(page.getByTestId('manage-shell')).toBeVisible()
      await expect(page.locator('.xt-manage__hamburger')).toBeVisible()
      if (center.testId) {
        await expect(page.getByTestId(center.testId)).toBeVisible()
      } else if (center.selector) {
        await expect(page.locator(center.selector)).toBeVisible()
      } else {
        await expect(page.getByText(center.text, { exact: true }).first()).toBeVisible()
      }
      await expectNoHorizontalOverflow(page)
    }
  }
})

test('factory center shows read-only production board and review actions', async ({ page }) => {
  await page.goto('/manage/factory')

  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByText('鑫泰铝业 数据中枢')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
  const detailToggle = page.getByRole('button', { name: /展开运行详情|收起运行详情/ })
  await expect(detailToggle).toBeVisible()
  if ((await detailToggle.textContent())?.includes('展开')) await detailToggle.click()
  await expect(page.getByText('今日产量')).toBeVisible()
  await expect(page.getByText('单吨能耗').first()).toBeVisible()
  await expect(page.getByText('交付状态')).toBeVisible()
  await expect(page.getByText('今日上报状态')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '车间' })).toBeVisible()
  await expect(page.getByText('挤压车间').first()).toBeVisible()
  await expect(page.getByTestId('delivery-missing-steps')).toBeVisible()
})
