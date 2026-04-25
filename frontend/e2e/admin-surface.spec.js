import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

async function loginAsAdmin(page) {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin')
  await page
    .getByTestId('login-password')
    .fill(process.env.PLAYWRIGHT_ADMIN_PASSWORD || process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong')
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/login') &&
    response.request().method() === 'POST' &&
    response.status() === 200
  )
  await page.getByTestId('login-submit').click()
  await loginResponse
}

test('admin surface is separate from review and entry surfaces', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin')

  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(page.getByTestId('admin-home')).toBeVisible()
  await expect(page.getByText('管理控制台').first()).toBeVisible()
  await expect(page.getByText('现场填报')).toHaveCount(0)
  await expect(page.getByText('数据接入与字段映射中心')).toBeVisible()
})

test('admin compatibility shortcuts land on reference command modules', async ({ page }) => {
  await loginAsAdmin(page)

  await page.goto('/admin/field-mapping')
  await expect(page).toHaveURL(/\/admin\/ingestion$/)
  await expect(page.getByTestId('review-ingestion-center-v2')).toBeVisible()
  await expect(page.getByTestId('review-ingestion-center-v2').getByRole('heading', { name: /06\s*数据接入与字段映射中心/ })).toBeVisible()

  await page.goto('/admin/ops')
  await expect(page).toHaveURL(/\/admin\/ops$/)
  await expect(page.getByTestId('live-dashboard')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="12"]').getByRole('heading', { name: '系统运维与观测' })).toBeVisible()

  await page.goto('/admin/master')
  await expect(page).toHaveURL(/\/admin\/master$/)
  await expect(page.getByTestId('admin-master-center')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="14"]').getByRole('heading', { name: '主数据与模板中心' })).toBeVisible()

  await page.goto('/admin/templates')
  await expect(page).toHaveURL(/\/admin\/master\/templates$/)
  await expect(page.getByTestId('template-editor-page')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="14"]').getByRole('heading', { name: '主数据与模板中心' })).toBeVisible()

  await page.goto('/admin/users')
  await expect(page).toHaveURL(/\/admin\/users$/)
  await expect(page.getByTestId('admin-users-center')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="13"]').getByRole('heading', { name: '权限与治理中心' })).toBeVisible()
})

test('admin ingestion route renders the mapping center smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin/ingestion')

  const ingestionCenter = page.getByTestId('review-ingestion-center-v2')
  const sourceTable = page.getByTestId('ingestion-source-table')
  const fieldTable = page.getByTestId('ingestion-field-table')
  const historyTable = page.getByTestId('ingestion-history-table')

  await expect(page).toHaveURL(/\/admin\/ingestion$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(ingestionCenter.getByRole('heading', { name: /06\s*数据接入与字段映射中心/ })).toBeVisible()
  await expect(ingestionCenter.getByText('管理端 / 配置治理面').first()).toBeVisible()
  await expect(ingestionCenter.locator('.mock-data-notice')).toContainText('fallback')
  await expect(sourceTable.getByText('数据源状态')).toBeVisible()
  await expect(fieldTable.getByText('字段映射表')).toBeVisible()
  await expect(historyTable.getByText('导入历史')).toBeVisible()
  await expect(ingestionCenter.getByText('成功率').first()).toBeVisible()
  await expect(fieldTable.getByRole('columnheader', { name: '校验状态' })).toBeVisible()
  await expect(ingestionCenter.getByRole('button', { name: '上传文件' })).toBeDisabled()
  await expect(ingestionCenter.getByRole('button', { name: '配置映射' })).toBeDisabled()
  await expect(ingestionCenter.getByRole('button', { name: '重新处理' }).last()).toBeDisabled()
  await expect(ingestionCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(ingestionCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
  await expect(ingestionCenter.getByText('MES 已正式联通')).toHaveCount(0)
  await expect(ingestionCenter.getByText('ERP 已正式同步')).toHaveCount(0)
  await expect(ingestionCenter.getByText('导入成功写入生产库')).toHaveCount(0)
})

test('fill-only operator cannot access admin ingestion', async ({ page }) => {
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

  await page.goto('/admin/ingestion')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-ingestion-center-v2')).toHaveCount(0)
})

test('super admin can switch from admin shell to entry and review shells', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin')

  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('button', { name: '录入端' }).click()
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()

  await page.goto('/admin')
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('button', { name: '审阅端' }).click()
  await expect(page).toHaveURL(/\/review\/overview$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
})
