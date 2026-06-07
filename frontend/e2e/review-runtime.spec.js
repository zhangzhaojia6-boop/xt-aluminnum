import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

async function seedStoredSession(page, token, user) {
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    localStorage.removeItem('aluminum_bypass_machine')
    sessionStorage.removeItem('aluminum_bypass_machine')
  }, { token, user })
}

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes('fill-only')) {
    const token = 'playwright-fill-token'
    const user = {
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

    await setupReviewSessionAndMocks(page, { token, user, skipLogin: true })
    await seedStoredSession(page, token, user)
    return
  }

  await setupReviewSessionAndMocks(page)
})

test('factory route renders the production board smoke surface', async ({ page }) => {
  await page.goto('/manage/production')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('manage-production')).toBeVisible()
  await expect(page.getByRole('heading', { name: '生产', exact: true })).toBeVisible()
  await expect(page.getByText('车间产量排名')).toBeVisible()
  await expect(page.getByText('生产摘要')).toBeVisible()
  await expect(page.getByTestId('manage-production-table')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '车间' })).toBeVisible()
  await expect(page.getByText('MES 已正式联通')).toHaveCount(0)
})

test('reports route renders the delivery center smoke surface', async ({ page }) => {
  await page.goto('/manage/reports')

  const reportsCenter = page.getByTestId('report-delivery-page')
  const deliveryTable = page.getByTestId('report-delivery-table')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(reportsCenter.getByRole('heading', { name: '日报与交付中心' })).toBeVisible()
  await expect(page.getByTestId('report-delivery-filters')).toBeVisible()
  await expect(reportsCenter.getByText('交付清单')).toBeVisible()
  await expect(deliveryTable).toBeVisible()
  await expect(deliveryTable.getByRole('columnheader', { name: '报告类型' })).toBeVisible()
  await expect(deliveryTable.getByRole('columnheader', { name: '当前状态' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '查询' })).toBeVisible()
  await expect(reportsCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(reportsCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('quality route renders the merged alerts smoke surface', async ({ page }) => {
  await page.goto('/manage/quality')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page).toHaveURL(/\/manage\/alerts.*(surface|domain)=quality/)
  await expect(page.getByTestId('manage-alerts')).toBeVisible()
  await expect(page.getByRole('heading', { name: '异常', exact: true })).toBeVisible()
  await expect(page.getByTestId('manage-alerts-filters')).toBeVisible()
  await expect(page.getByTestId('manage-alert-work-queues')).toBeVisible()
  await expect(page.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('cost route redirects to yesterday report instead of retired cost center', async ({ page }) => {
  await page.goto('/manage/factory/cost')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page).toHaveURL(/\/manage\/today$/)
  await expect(page.getByRole('heading', { name: '工厂总览' })).toBeVisible()
  await expect(page.getByText('成本核算与效益中心')).toHaveCount(0)
})

test('brain route renders the AI control smoke surface', async ({ page }) => {
  await page.goto('/manage/ai-assistant')

  const aiWorkstation = page.locator('.ai-workstation')
  const manageShell = page.getByTestId('manage-shell')

  await expect(manageShell).toBeVisible()
  await expect(manageShell.getByRole('button', { name: 'AI 助手' })).toBeVisible()
  await expect(manageShell.getByRole('button', { name: '搜索 Ctrl K' })).toBeVisible()
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
  await expect(page.getByTestId('manage-alerts')).toHaveCount(0)
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

test('ops reliability center route renders system settings surface', async ({ page }) => {
  await page.goto('/manage/production')
  await expect(page.getByTestId('manage-shell')).toBeVisible()

  await page.goto('/manage/admin/settings')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
})

test('review roadmap legacy path redirects to yesterday report', async ({ page }) => {
  await page.goto('/review/roadmap')

  await expect(page).toHaveURL(/\/manage\/today$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂总览' })).toBeVisible()
})

test('review navigation does not expose roadmap as a formal center', async ({ page }) => {
  await page.goto('/manage/today')

  const reviewAside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  const roadmapItem = reviewAside.locator('.xt-manage__nav-item', { hasText: '路线图' })

  await expect(reviewAside.locator('.xt-manage__nav-group-label', { hasText: '昨日报表' })).toBeVisible()
  await expect(roadmapItem).toHaveCount(0)
})
