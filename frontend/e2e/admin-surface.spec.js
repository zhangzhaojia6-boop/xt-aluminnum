import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

async function loginAsAdmin(page) {
  await setupReviewSessionAndMocks(page, {
    token: 'playwright-admin-token',
    user: {
      id: 1,
      username: 'admin',
      name: 'Playwright Admin',
      role: 'admin',
      is_mobile_user: true,
      is_reviewer: true,
      is_manager: true,
      data_scope_type: 'all',
      assigned_shift_ids: []
    }
  })
}

test('admin surface is separate from review and entry surfaces', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂实时态势' })).toBeVisible()
  await expect(page.locator('.xt-placeholder-page')).toHaveCount(0)
  await expect(page.getByText('现场填报')).toHaveCount(0)
  await expect(page.getByTestId('entry-shell')).toHaveCount(0)
})

test('admin compatibility shortcuts land on manage modules', async ({ page }) => {
  await loginAsAdmin(page)

  await page.goto('/manage/ingestion')
  await expect(page).toHaveURL(/\/manage\/ingestion$/)
  await expect(page.getByTestId('review-ingestion-center-v2')).toBeVisible()
  await expect(page.getByRole('heading', { name: '数据接入与字段映射中心' })).toBeVisible()

  await page.goto('/manage/admin/settings')
  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工厂实时态势' })).toBeVisible()

  await page.goto('/manage/master')
  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('admin-master-center')).toBeVisible()
  await expect(page.getByRole('heading', { name: '车间主数据' })).toBeVisible()

  await page.goto('/manage/admin/templates')
  await expect(page).toHaveURL(/\/manage\/admin\/templates$/)
  await expect(page.getByTestId('template-editor-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '主数据与模板中心' })).toBeVisible()

  await page.goto('/manage/admin/users')
  await expect(page).toHaveURL(/\/manage\/admin\/users$/)
  await expect(page.getByRole('heading', { name: /权限治理中心|用户管理/ })).toBeVisible()
})

test('admin master route renders the master data smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/master')

  const masterCenter = page.getByTestId('admin-master-center')
  const adminAside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')

  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(adminAside.locator('.xt-manage__nav-item.is-active', { hasText: '主数据' })).toBeVisible()
  await expect(adminAside.getByRole('link', { name: '设置 运行' })).toHaveCount(0)
  await expect(adminAside.getByRole('link', { name: '别名 模板' })).toHaveCount(0)
  await expect(adminAside.getByRole('link', { name: '导入 接入' })).toHaveCount(0)
  await expect(masterCenter.getByRole('heading', { name: '车间主数据' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '新增车间' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '编码' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '名称' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(masterCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('admin ingestion route renders the mapping center smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/ingestion')

  const ingestionCenter = page.getByTestId('review-ingestion-center-v2')

  await expect(page).toHaveURL(/\/manage\/ingestion$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(ingestionCenter.getByRole('heading', { name: '数据接入与字段映射中心' })).toBeVisible()
  await expect(ingestionCenter.getByText('导入批次')).toBeVisible()
  await expect(ingestionCenter.getByText('总成功率')).toBeVisible()
  await expect(ingestionCenter.getByText('导入执行')).toBeVisible()
  await expect(ingestionCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(ingestionCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('admin ops route renders the observability smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin/settings')

  const opsCenter = page.getByTestId('live-dashboard')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(opsCenter.getByRole('heading', { name: '工厂实时态势' })).toBeVisible()
  await expect(opsCenter.getByText('今日产量').first()).toBeVisible()
  await expect(opsCenter.getByText('成材率').first()).toBeVisible()
  await expect(opsCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(opsCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('admin ops route shows live fill and external MES binding status without overflow', async ({ page }) => {
  await loginAsAdmin(page)

  for (const viewport of [
    { width: 1366, height: 820 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/manage/admin/settings?desktop=1')

    const strip = page.locator('.live-reality-strip')
    await expect(strip).toBeVisible()
    await expect(strip.getByText('实时数据日期')).toBeVisible()
    await expect(strip.getByText('当前显示 2026-05-12')).toBeVisible()
    await expect(strip.getByText('今天 2026-05-13 暂无填报')).toBeVisible()
    await expect(strip.getByText('外部 MES 机列绑定')).toBeVisible()
    await expect(strip.getByText('已绑机列 22 卷')).toBeVisible()
    await expect(strip.getByText('上游机列码缺失 21 行 · 待归属 0 卷')).toBeVisible()

    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth
    ))
    expect(overflow).toBeLessThanOrEqual(1)
  }
})

test('admin ops route displays external missing input checklist without overflow', async ({ page }) => {
  await loginAsAdmin(page)
  await page.route('**/api/v1/dashboard/external-readiness', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        hard_gate_passed: false,
        module_usable: false,
        external_connection_enabled: false,
        hard_issues: [
          {
            level: 'hard',
            code: 'LLM_DISABLED',
            required_env: ['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY']
          }
        ],
        warning_issues: [],
        missing_inputs: [
          {
            issue_code: 'LLM_DISABLED',
            level: 'hard',
            purpose: 'LLM/AI 摘要增强',
            location: '服务器 backend/.env',
            missing_fields: ['LLM_ENABLED', 'LLM_API_BASE', 'LLM_API_KEY'],
            impact: 'AI 摘要与分析增强不可用，不能宣称 AI 能力正式联通。',
            suggested_value: 'LLM_ENABLED=true；LLM_API_KEY=<redacted>'
          }
        ]
      })
    })
  })

  for (const viewport of [
    { width: 1366, height: 820 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/manage/admin/settings?desktop=1')

    const checklist = page.locator('.external-readiness-missing')
    await expect(checklist).toBeVisible()
    await expect(checklist.getByText('缺失输入清单')).toBeVisible()
    await expect(checklist.getByText('LLM/AI 摘要增强')).toBeVisible()
    await expect(checklist.locator('.external-readiness-missing__fields').getByText('LLM_API_KEY', { exact: true })).toBeVisible()
    await expect(checklist.getByText('<redacted>')).toBeVisible()
    await expect(page.getByText('real-secret')).toHaveCount(0)

    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth
    ))
    expect(overflow).toBeLessThanOrEqual(1)
  }
})

test('admin governance route renders the permission governance smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin/governance')

  const governanceCenter = page.getByTestId('review-governance-center')

  await expect(page).toHaveURL(/\/manage\/admin\/governance$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(governanceCenter.getByRole('heading', { name: '权限与治理中心' })).toBeVisible()
  await expect(governanceCenter.getByText('当前角色')).toBeVisible()
  await expect(governanceCenter.getByText('数据范围')).toBeVisible()
  await expect(governanceCenter.getByText('能力矩阵')).toBeVisible()
  await expect(governanceCenter.getByText('审阅权限')).toBeVisible()
  await expect(governanceCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(governanceCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('fill-only operator cannot access admin master ops ingestion or governance', async ({ page }) => {
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

  await page.goto('/manage/master')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.getByTestId('admin-master-center')).toHaveCount(0)

  await page.goto('/manage/ingestion')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-ingestion-center-v2')).toHaveCount(0)

  await page.goto('/manage/admin/settings')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.getByTestId('live-dashboard')).toHaveCount(0)

  await page.goto('/manage/admin/governance')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-governance-center')).toHaveCount(0)
})

test('manager lands in manage shell without admin navigation', async ({ page }) => {
  await setupReviewSessionAndMocks(page, {
    token: 'playwright-review-manager-token',
    user: {
      id: 3,
      username: 'review-manager',
      name: 'Playwright Review Manager',
      role: 'manager',
      is_mobile_user: false,
      is_reviewer: true,
      is_manager: true,
      data_scope_type: 'all',
      assigned_shift_ids: []
    }
  })

  await page.goto('/manage/overview')

  await expect(page).toHaveURL(/\/manage\/overview$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  const manageSidebar = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  await expect(manageSidebar.getByRole('link', { name: '主数据 模板' })).toHaveCount(0)
  await expect(manageSidebar.getByRole('link', { name: '数据接入 接入' })).toHaveCount(0)
  await expect(manageSidebar.getByRole('link', { name: '设置 运行' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '管理端' })).toHaveCount(0)

  await page.goto('/manage/master')
  await expect(page).toHaveURL(/\/manage\/overview$/)
  await expect(page.getByTestId('admin-master-center')).toHaveCount(0)
})

test('super admin can switch between admin entry and review surfaces', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await loginAsAdmin(page)
  await page.goto('/manage/admin')

  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await page.goto('/entry')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()

  await page.goto('/manage/admin')
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await page.goto('/manage/overview')
  await expect(page).toHaveURL(/\/manage\/overview$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
})
