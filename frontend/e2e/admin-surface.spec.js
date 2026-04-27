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
  await expect(page.getByTestId('live-dashboard').getByRole('heading', { name: /12\s*系统运维与可观测/ })).toBeVisible()

  await page.goto('/admin/master')
  await expect(page).toHaveURL(/\/admin\/master$/)
  await expect(page.getByTestId('admin-master-center')).toBeVisible()
  await expect(page.getByTestId('admin-master-center').getByRole('heading', { name: /14\s*主数据与模板中心/ })).toBeVisible()

  await page.goto('/admin/templates')
  await expect(page).toHaveURL(/\/admin\/master\/templates$/)
  await expect(page.getByTestId('template-editor-page')).toBeVisible()
  await expect(page.getByTestId('admin-master-center').getByRole('heading', { name: /14\s*主数据与模板中心/ })).toBeVisible()

  await page.goto('/admin/users')
  await expect(page).toHaveURL(/\/admin\/users$/)
  await expect(page.getByTestId('admin-users-center')).toBeVisible()
  await expect(page.locator('.reference-page[data-module="13"]').getByRole('heading', { name: /权限(与)?治理中心/ })).toBeVisible()
})

test('admin master route renders the master data and template smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin/master')

  const masterCenter = page.getByTestId('admin-master-center')
  const categoryTable = page.getByTestId('master-category-table')
  const templateTable = page.getByTestId('master-template-table')
  const fieldRuleTable = page.getByTestId('master-field-rule-table')
  const riskTable = page.getByTestId('master-risk-table')

  await expect(page).toHaveURL(/\/admin\/master$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  const adminAside = page.getByTestId('admin-shell').locator('.app-shell__aside')
  await expect(adminAside).toBeVisible()
  await expect(adminAside.locator('.el-menu-item.is-active', { hasText: '主数据' })).toBeVisible()
  await expect(adminAside.getByText('系统运维')).toBeVisible()
  await expect(masterCenter.getByRole('heading', { name: /14\s*主数据与模板中心/ })).toBeVisible()
  await expect(masterCenter.getByText('trial / 管理端主数据配置面')).toBeVisible()
  await expect(masterCenter.locator('.mock-data-notice')).toContainText('fallback')
  await expect(categoryTable).toBeVisible()
  await expect(categoryTable.getByText('车间').first()).toBeVisible()
  await expect(categoryTable.getByText('班组').first()).toBeVisible()
  await expect(categoryTable.getByText('机台').first()).toBeVisible()
  await expect(templateTable).toBeVisible()
  await expect(templateTable.getByText('模板配置')).toBeVisible()
  await expect(templateTable.getByText('主操填报模板')).toBeVisible()
  await expect(fieldRuleTable).toBeVisible()
  await expect(fieldRuleTable.getByText(/字段规则|字段 owner/).first()).toBeVisible()
  await expect(fieldRuleTable.getByText('owner-only 字段，不下发给普通班组')).toBeVisible()
  await expect(riskTable).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '导出配置' })).toBeDisabled()
  await expect(masterCenter.getByRole('button', { name: '发布模板' })).toBeDisabled()
  await expect(masterCenter.getByRole('button', { name: '保存字段规则' })).toBeDisabled()
  await expect(masterCenter.getByRole('button', { name: '刷新主数据' })).toBeEnabled()
  await expect(masterCenter.getByText('主数据已保存成功')).toHaveCount(0)
  await expect(masterCenter.getByText('模板已发布成功')).toHaveCount(0)
  await expect(masterCenter.getByText('字段规则已同步成功')).toHaveCount(0)
  await expect(masterCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(masterCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
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

  await expect(sourceTable.getByText('在制料快照')).toBeVisible()
  await expect(fieldTable.getByText('wip_ton')).toBeVisible()
  await expect(sourceTable.getByText('待正式对接')).toBeVisible()
})

test('admin ops route renders the observability smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin/ops')

  const opsCenter = page.getByTestId('live-dashboard')
  const serviceTable = page.getByTestId('ops-service-table')
  const riskTable = page.getByTestId('ops-risk-table')

  await expect(page).toHaveURL(/\/admin\/ops$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(opsCenter.getByRole('heading', { name: /12\s*系统运维与可观测/ })).toBeVisible()
  await expect(opsCenter.getByText('管理端 / 运维观测面')).toBeVisible()
  await expect(opsCenter.getByText(/healthz|健康/).first()).toBeVisible()
  await expect(opsCenter.getByText(/readyz|就绪/).first()).toBeVisible()
  await expect(opsCenter.getByText(/hard gate|上线闸门/).first()).toBeVisible()
  await expect(opsCenter.getByText('错误率').first()).toBeVisible()
  await expect(opsCenter.getByText('响应时间').first()).toBeVisible()
  await expect(opsCenter.getByText(/Mock|fallback|mixed|source/).first()).toBeVisible()
  await expect(serviceTable).toBeVisible()
  await expect(serviceTable.getByRole('columnheader', { name: '延迟' })).toBeVisible()
  await expect(serviceTable.getByText('AI probe')).toBeVisible()
  await expect(riskTable).toBeVisible()
  await expect(opsCenter.getByRole('button', { name: '查看回滚预检' }).first()).toBeDisabled()
  await expect(opsCenter.getByRole('button', { name: '导出诊断' })).toBeDisabled()
  await expect(opsCenter.getByRole('button', { name: '查看日志' })).toBeDisabled()
  await expect(opsCenter.getByText('已自动修复')).toHaveCount(0)
  await expect(opsCenter.getByText('已真实回滚')).toHaveCount(0)
  await expect(opsCenter.getByText('已执行部署成功')).toHaveCount(0)
})

test('admin governance route renders the permission governance smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin/governance')

  const governanceCenter = page.getByTestId('admin-governance-center')
  const roleMatrix = page.getByTestId('governance-role-matrix')
  const auditTable = page.getByTestId('governance-audit-table')
  const riskTable = page.getByTestId('governance-risk-table')

  await expect(page).toHaveURL(/\/admin\/governance$/)
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(governanceCenter.getByRole('heading', { name: /13\s*权限治理中心/ })).toBeVisible()
  await expect(governanceCenter.getByText('管理端 / 权限治理面')).toBeVisible()
  await expect(governanceCenter.getByText('角色矩阵').first()).toBeVisible()
  await expect(governanceCenter.getByText('审计日志').first()).toBeVisible()
  await expect(governanceCenter.getByText('数据权限').first()).toBeVisible()
  await expect(governanceCenter.getByText(/高风险账号|治理风险/).first()).toBeVisible()
  await expect(governanceCenter.getByText(/Mock|fallback|mixed|source/).first()).toBeVisible()
  await expect(roleMatrix).toBeVisible()
  await expect(roleMatrix.getByRole('columnheader', { name: '可访问端' })).toBeVisible()
  await expect(roleMatrix.getByText('admin').first()).toBeVisible()
  await expect(roleMatrix.getByText('fill-only').first()).toBeVisible()
  await expect(auditTable).toBeVisible()
  await expect(auditTable.getByRole('columnheader', { name: '风险级别' })).toBeVisible()
  await expect(riskTable).toBeVisible()
  await expect(governanceCenter.getByRole('button', { name: '导出审计' })).toBeDisabled()
  await expect(governanceCenter.getByRole('button', { name: '保存策略' })).toBeDisabled()
  await expect(governanceCenter.getByText('权限已保存成功')).toHaveCount(0)
  await expect(governanceCenter.getByText('安全策略已生效')).toHaveCount(0)
  await expect(governanceCenter.getByText('审计日志已清理')).toHaveCount(0)
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

  await page.goto('/admin/master')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('admin-master-center')).toHaveCount(0)

  await page.goto('/admin/ingestion')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('review-ingestion-center-v2')).toHaveCount(0)

  await page.goto('/admin/ops')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('live-dashboard')).toHaveCount(0)

  await page.goto('/admin/governance')

  await expect(page).toHaveURL(/\/(entry|login)$/)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
  await expect(page.getByTestId('admin-governance-center')).toHaveCount(0)
})

test('manager without admin access cannot see admin master ops or governance entry', async ({ page }) => {
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

  await page.goto('/review/overview')

  await expect(page).toHaveURL(/\/review\/overview$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByText(/主数据与模板中心|主数据配置面/)).toHaveCount(0)
  await expect(page.getByText(/系统运维与可观测|系统运维与观测|系统运维/)).toHaveCount(0)
  await expect(page.getByText(/权限治理中心|权限与治理中心|权限治理/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '管理端' })).toHaveCount(0)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
})

test('super admin can switch from admin shell to entry and review shells', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/admin')

  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('button', { name: '录入端', exact: true }).click()
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()

  await page.goto('/admin')
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('button', { name: '审阅端' }).click()
  await expect(page).toHaveURL(/\/review\/overview$/)
  await expect(page.getByTestId('review-shell')).toBeVisible()
})
