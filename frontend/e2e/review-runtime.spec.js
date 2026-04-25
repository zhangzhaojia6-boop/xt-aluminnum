import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

test('factory route renders the production board smoke surface', async ({ page }) => {
  await page.goto('/review/factory')

  const factoryBoard = page.getByTestId('factory-dashboard')
  const lineTable = page.getByTestId('factory-line-table')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(factoryBoard.getByRole('heading', { name: /05\s*工厂作业看板/ })).toBeVisible()
  await expect(factoryBoard.getByRole('button', { name: '刷新' })).toBeVisible()
  await expect(lineTable).toBeVisible()
  await expect(lineTable.getByRole('columnheader', { name: '异常' })).toBeVisible()
  await expect(lineTable.getByRole('columnheader', { name: '趋势（24h）' })).toBeVisible()
  await expect(lineTable.getByText('铸造一线')).toBeVisible()
  await expect(factoryBoard.getByText('风险摘要')).toBeVisible()
})

test('ops reliability center route renders live dashboard surface', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-shell')).toBeVisible()

  await page.goto('/review/ops-reliability')

  await expect(page).toHaveURL(/\/admin\/ops$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.getByText('系统运维与观测', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.live-dashboard .stat-card').first()).toBeVisible()
})

test('review roadmap legacy path redirects to review overview', async ({ page }) => {
  await page.goto('/review/roadmap')

  await expect(page).toHaveURL(/\/review\/overview$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('overview-dashboard')).toBeVisible()
})

test('review navigation does not expose roadmap as a formal center', async ({ page }) => {
  await page.goto('/review/overview')

  const reviewAside = page.getByTestId('review-shell').locator('.app-shell__aside')
  const roadmapItem = reviewAside.locator('.el-menu-item', { hasText: '路线图' })

  await expect(reviewAside.locator('.app-nav-group__title', { hasText: '经营与智能' })).toBeVisible()
  await expect(roadmapItem).toHaveCount(0)
})
