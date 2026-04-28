import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

async function expectFactoryCenter(page) {
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.locator('.xt-manage__brand')).toContainText('鑫')
  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂作业看板' })).toBeVisible()
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
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

test('factory center shows read-only production board and review actions', async ({ page }) => {
  await page.goto('/manage/factory')

  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByText('鑫泰铝业协同运营平台')).toBeVisible()
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
