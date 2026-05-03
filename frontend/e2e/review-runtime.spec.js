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
  await page.goto('/manage/factory')

  const factoryBoard = page.getByTestId('factory-dashboard')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(factoryBoard.getByRole('heading', { name: '工厂作业看板' })).toBeVisible()
  await expect(factoryBoard.getByText('鑫泰铝业 数据中枢')).toBeVisible()
  await expect(factoryBoard.getByTestId('review-home-hero')).toBeVisible()
  await expect(factoryBoard.getByTestId('review-assistant-dock')).toBeVisible()
  const detailToggle = factoryBoard.getByRole('button', { name: /展开运行详情|收起运行详情/ })
  await expect(detailToggle).toBeVisible()
  if ((await detailToggle.textContent())?.includes('展开')) await detailToggle.click()
  await expect(factoryBoard.getByText('今日产量').first()).toBeVisible()
  await expect(factoryBoard.getByText('单吨能耗').first()).toBeVisible()
  await expect(factoryBoard.getByTestId('delivery-ready-card')).toBeVisible()
  await expect(factoryBoard.getByText('未就绪')).toBeVisible()

  await expect(factoryBoard.getByText('今日上报状态')).toBeVisible()
  await expect(factoryBoard.getByRole('columnheader', { name: '车间' })).toBeVisible()
  await expect(factoryBoard.getByText('挤压车间').first()).toBeVisible()
  await expect(factoryBoard.getByTestId('delivery-missing-steps')).toBeVisible()
  await expect(factoryBoard.getByText('MES 已正式联通')).toHaveCount(0)
})

test('reports route renders the delivery center smoke surface', async ({ page }) => {
  await page.goto('/manage/reports')

  const reportsCenter = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '日报与交付中心' }) })
  const deliveryTable = reportsCenter.locator('.el-table')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(reportsCenter.getByRole('heading', { name: '日报与交付中心' })).toBeVisible()
  await expect(reportsCenter.getByText('日报筛选')).toBeVisible()
  await expect(reportsCenter.getByText('交付清单')).toBeVisible()
  await expect(deliveryTable).toBeVisible()
  await expect(deliveryTable.getByRole('columnheader', { name: '报告类型' })).toBeVisible()
  await expect(deliveryTable.getByRole('columnheader', { name: '当前状态' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '查询' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(reportsCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('quality route renders the quality alerts smoke surface', async ({ page }) => {
  await page.goto('/manage/quality')

  const qualityCenter = page.locator('.reference-page').filter({ has: page.getByRole('heading', { name: '质量与告警中心' }) })
  const alertTable = qualityCenter.locator('.el-table')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(qualityCenter.getByRole('heading', { name: '质量与告警中心' })).toBeVisible()
  await expect(qualityCenter.getByText('告警筛选')).toBeVisible()
  await expect(qualityCenter.getByText('告警清单')).toBeVisible()
  await expect(alertTable).toBeVisible()
  await expect(alertTable.getByRole('columnheader', { name: '问题级别' })).toBeVisible()
  await expect(alertTable.getByRole('columnheader', { name: '处理状态' })).toBeVisible()
  await expect(qualityCenter.getByRole('button', { name: '运行质量检查' })).toBeVisible()
  await expect(qualityCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(qualityCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('cost route renders the factory cost benefit smoke surface', async ({ page }) => {
  await page.goto('/manage/factory/cost')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '经营效益' })).toBeVisible()
  await expect(page.getByText('经营估算')).toBeVisible()
  await expect(page.getByText('毛差估算')).toBeVisible()
  await expect(page.getByText('待补口径')).toBeVisible()
  await expect(page.getByText('成本核算与效益中心')).toHaveCount(0)
})

test('brain route renders the AI control smoke surface', async ({ page }) => {
  await page.goto('/manage/ai-assistant')

  const aiWorkstation = page.locator('.ai-workstation')
  const reviewAside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(reviewAside).toBeVisible()
  await expect(reviewAside.locator('.xt-manage__nav-item.is-active', { hasText: 'AI 助手' })).toBeVisible()
  await expect(reviewAside.getByRole('link', { name: '工厂总览 全局' })).toBeVisible()
  await expect(aiWorkstation).toBeVisible()
  await expect(aiWorkstation.getByRole('heading', { name: 'AI 工作台' })).toBeVisible()
  await expect(aiWorkstation.getByText(/对话|暂无对话|加载中/).first()).toBeVisible()
  await expect(aiWorkstation.getByPlaceholder('问 AI 总管：今天哪个车间风险最高，下一步怎么做？')).toBeVisible()
  await expect(aiWorkstation.getByRole('button', { name: '新建' })).toBeVisible()
  await expect(aiWorkstation.getByRole('button', { name: '发送' })).toBeDisabled()
  await expect(aiWorkstation.getByText('AI 已自动处理')).toHaveCount(0)
  await expect(aiWorkstation.getByText('AI 已接管生产')).toHaveCount(0)
  await expect(aiWorkstation.getByText('自动排产完成')).toHaveCount(0)
  await expect(aiWorkstation.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(aiWorkstation.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('fill-only operator cannot access review reports', async ({ page }) => {
  await page.goto('/manage/reports')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
})

test('fill-only operator cannot access review quality', async ({ page }) => {
  await page.goto('/manage/quality')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.reference-page').filter({ hasText: '质量与告警中心' })).toHaveCount(0)
})

test('fill-only operator cannot access review cost', async ({ page }) => {
  await page.goto('/manage/cost')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-cost-center')).toHaveCount(0)
})

test('fill-only operator cannot access review brain', async ({ page }) => {
  await page.goto('/manage/ai')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.locator('.ai-workstation')).toHaveCount(0)
  const entryShell = page.getByTestId('entry-shell')
  if (await entryShell.count()) {
    await expect(entryShell.getByText('AI 工作台')).toHaveCount(0)
    await expect(entryShell.getByText('管理端')).toHaveCount(0)
  }
})

test('ops reliability center route renders live dashboard surface', async ({ page }) => {
  await page.goto('/manage/factory')
  await expect(page.getByTestId('manage-shell')).toBeVisible()

  await page.goto('/manage/admin/settings')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.getByText('工厂实时态势', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('今日产量').first()).toBeVisible()
})

test('review roadmap legacy path redirects to review overview', async ({ page }) => {
  await page.goto('/review/roadmap')

  await expect(page).toHaveURL(/\/manage\/overview$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂总览' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: '工厂指挥导航' })).toBeVisible()
})

test('review navigation does not expose roadmap as a formal center', async ({ page }) => {
  await page.goto('/manage/overview')

  const reviewAside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  const roadmapItem = reviewAside.locator('.xt-manage__nav-item', { hasText: '路线图' })

  await expect(reviewAside.locator('.xt-manage__nav-group-label', { hasText: '工厂状态' })).toBeVisible()
  await expect(roadmapItem).toHaveCount(0)
})
