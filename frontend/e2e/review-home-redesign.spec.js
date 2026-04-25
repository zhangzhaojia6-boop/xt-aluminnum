import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

async function expectFactoryCenter(page) {
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('review-brand-mark')).toBeVisible()
  await expect(page.getByTestId('review-brand-title')).toContainText('鑫泰铝业')
  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(page.getByRole('heading', { name: /05\s*工厂作业看板/ })).toBeVisible()
  await expect(page.getByTestId('factory-line-table')).toBeVisible()
  await expect(page.getByRole('heading', { name: '风险摘要' })).toBeVisible()
}

test('review shell keeps the factory center readable across desktop tablet and mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/review/factory')
  await expectFactoryCenter(page)

  await page.setViewportSize({ width: 900, height: 1180 })
  await expectFactoryCenter(page)

  await page.setViewportSize({ width: 430, height: 932 })
  await expectFactoryCenter(page)
})

test('factory center shows read-only production board and review actions', async ({ page }) => {
  await page.goto('/review/factory')

  const lineTable = page.getByTestId('factory-line-table')

  await expect(page.getByTestId('factory-dashboard')).toBeVisible()
  await expect(lineTable.getByRole('columnheader', { name: '车间 / 产线' })).toBeVisible()
  await expect(lineTable.getByRole('columnheader', { name: '异常' })).toBeVisible()
  await expect(lineTable.getByRole('columnheader', { name: '趋势（24h）' })).toBeVisible()
  await expect(lineTable.getByText('铸造一线')).toBeVisible()
  await expect(page.getByText('本页不承接生产事实写入', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '去审阅' })).toBeVisible()
  await expect(page.getByRole('button', { name: '看质量告警' })).toBeVisible()
  await expect(page.getByRole('button', { name: '查看日报' })).toBeVisible()
})
