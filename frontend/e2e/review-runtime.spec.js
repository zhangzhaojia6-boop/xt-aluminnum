import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes('fill-only')) {
    await setupReviewSessionAndMocks(page, {
      token: 'playwright-fill-token',
      user: {
        id: 2,
        username: 'operator',
        name: 'Playwright Operator',
        role: 'operator',
        is_mobile_user: true,
        is_reviewer: false,
        is_manager: false,
        data_scope_type: 'self_team',
        assigned_shift_ids: []
      }
    })
    return
  }

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

test('reports route renders the delivery center smoke surface', async ({ page }) => {
  await page.goto('/review/reports')

  const reportsCenter = page.getByTestId('reports-delivery-center')
  const deliveryTable = page.getByTestId('reports-delivery-table')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(reportsCenter.getByRole('heading', { name: /08\s*日报与交付中心/ })).toBeVisible()
  await expect(reportsCenter.getByText('fallback').first()).toBeVisible()
  await expect(reportsCenter.getByText('交付清单')).toBeVisible()
  await expect(deliveryTable).toBeVisible()
  await expect(deliveryTable.getByRole('columnheader', { name: '生成口径' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '导出 PDF' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '导出 Excel' })).toBeVisible()
  await expect(reportsCenter.getByText(/auto_confirmed|已自动确认/).first()).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(reportsCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('quality route renders the quality alerts smoke surface', async ({ page }) => {
  await page.goto('/review/quality')

  const qualityCenter = page.getByTestId('quality-alerts-center')
  const alertTable = page.getByTestId('quality-alert-table')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(qualityCenter.getByRole('heading', { name: /09\s*质量与告警中心/ })).toBeVisible()
  await expect(qualityCenter.getByText('fallback').first()).toBeVisible()
  await expect(qualityCenter.getByText('告警列表')).toBeVisible()
  await expect(alertTable).toBeVisible()
  await expect(alertTable.getByRole('columnheader', { name: '严重度' })).toBeVisible()
  await expect(alertTable.getByText(/待处置|处理中/).first()).toBeVisible()
  await expect(qualityCenter.getByText('AI 辅助分诊')).toBeVisible()
  await expect(qualityCenter.getByText('辅助建议').first()).toBeVisible()
  await expect(qualityCenter.getByRole('button', { name: '进入审阅任务' })).toBeVisible()
  await expect(qualityCenter.getByRole('button', { name: '查看日报影响' })).toBeVisible()
  await expect(qualityCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(qualityCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('cost route renders the cost benefit smoke surface', async ({ page }) => {
  await page.goto('/review/cost-accounting')

  const costCenter = page.getByTestId('cost-benefit-center')
  const detailTable = page.getByTestId('cost-detail-table')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(costCenter.getByRole('heading', { name: /10\s*成本核算与效益中心/ })).toBeVisible()
  await expect(costCenter.getByText(/经营估算|策略口径/).first()).toBeVisible()
  await expect(costCenter.getByText('fallback').first()).toBeVisible()
  await expect(costCenter.getByText('吨铝成本')).toBeVisible()
  await expect(costCenter.getByText('电耗').first()).toBeVisible()
  await expect(costCenter.getByText('天然气').first()).toBeVisible()
  await expect(costCenter.getByRole('button', { name: '产量口径' })).toBeVisible()
  await expect(costCenter.getByRole('button', { name: '通货口径' })).toBeVisible()
  await expect(detailTable).toBeVisible()
  await expect(detailTable.getByRole('columnheader', { name: '吨耗 / 吨成本' })).toBeVisible()
  await expect(costCenter.getByText('成本构成趋势')).toBeVisible()
  await expect(costCenter.getByRole('button', { name: '查看日报影响' })).toBeVisible()
  await expect(costCenter.getByRole('button', { name: '查看质量风险' })).toBeVisible()
  await expect(costCenter.getByText('财务结算完成')).toHaveCount(0)
  await expect(costCenter.getByText('月结完成')).toHaveCount(0)
  await expect(costCenter.getByText('ERP 已入账')).toHaveCount(0)
  await expect(costCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(costCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('fill-only operator cannot access review reports', async ({ page }) => {
  await page.goto('/review/reports')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('review-shell')).toHaveCount(0)
})

test('fill-only operator cannot access review quality', async ({ page }) => {
  await page.goto('/review/quality')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('review-shell')).toHaveCount(0)
  await expect(page.getByTestId('quality-alerts-center')).toHaveCount(0)
})

test('fill-only operator cannot access review cost', async ({ page }) => {
  await page.goto('/review/cost-accounting')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('review-shell')).toHaveCount(0)
  await expect(page.getByTestId('cost-benefit-center')).toHaveCount(0)
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
