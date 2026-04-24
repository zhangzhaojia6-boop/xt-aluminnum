import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

test('review shell renders cute runtime robots and risk layer', async ({ page }) => {
  await page.goto('/review/factory')

  const runtimeFlow = page.getByTestId('agent-runtime-flow')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(runtimeFlow).toBeVisible()
  await expect(runtimeFlow.getByText('算法流水线').first()).toBeVisible()
  await expect(runtimeFlow.getByText('分析决策助手').first()).toBeVisible()
  await expect(runtimeFlow.getByText('执行交付助手').first()).toBeVisible()
  await expect(runtimeFlow.getByText('可靠度', { exact: true })).toBeVisible()
  await expect(runtimeFlow.getByText('风险级别', { exact: true })).toBeVisible()
  await expect(runtimeFlow.getByText('阻塞项', { exact: true })).toBeVisible()
  await expect(runtimeFlow.getByText('异常数', { exact: true })).toBeVisible()
  await expect(page.locator('span.panel-source-tag', { hasText: '算法流水线 · 确定性规则' })).not.toHaveCount(0)
  await expect(page.locator('span.panel-source-tag', { hasText: '分析决策助手 · 解释与建议' })).not.toHaveCount(0)
  await expect(page.locator('span.panel-source-tag', { hasText: '执行交付助手 · 闭环执行' })).not.toHaveCount(0)

  await page.goto('/review/workshop')
  await expect(page.getByTestId('workshop-dashboard').getByRole('heading', { name: '车间审阅端' })).toBeVisible()
  const productionTable = page.locator('.review-workshop__layers .el-table').first()
  await expect(productionTable.locator('thead th', { hasText: '来源' })).toBeVisible()
  await expect(productionTable.getByText('主操直录').first()).toBeVisible()
  await expect(productionTable.getByText('专项补录')).toHaveCount(0)
  await expect(page.getByText('owner_only')).toHaveCount(0)
})

test('ops reliability center route renders live dashboard surface', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-shell')).toBeVisible()

  await page.goto('/review/ops-reliability')

  await expect(page).toHaveURL(/\/admin\/ops-reliability$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.getByText('系统运维与可观测', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.live-dashboard .stat-card').first()).toBeVisible()
})

test('review roadmap stays in review shell as reference module 16', async ({ page }) => {
  await page.goto('/review/roadmap')

  await expect(page).toHaveURL(/\/review\/roadmap$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-roadmap-center')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="16"]').getByRole('heading', { name: '路线图与下一步' })).toBeVisible()
})

test('review navigation exposes roadmap as a formal command module', async ({ page }) => {
  await page.goto('/review/overview')

  const reviewAside = page.getByTestId('review-shell').locator('.app-shell__aside')
  const roadmapItem = reviewAside.locator('.el-menu-item', { hasText: '路线图' })

  await expect(reviewAside.locator('.app-nav-group__title', { hasText: '经营与智能' })).toBeVisible()
  await expect(roadmapItem).toBeVisible()
  await roadmapItem.click()
  await expect(page).toHaveURL(/\/review\/roadmap$/)
  await expect(page.getByTestId('review-roadmap-center')).toBeVisible()
})
