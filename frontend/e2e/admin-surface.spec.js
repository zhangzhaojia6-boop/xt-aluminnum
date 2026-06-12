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

async function loginAsFillOnlyOperator(page) {
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
}

test('admin surface is separate from review and entry surfaces', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  await expect(page.locator('.xt-placeholder-page')).toHaveCount(0)
  await expect(page.getByText('现场填报')).toHaveCount(0)
  await expect(page.getByTestId('entry-shell')).toHaveCount(0)
})

test('admin compatibility shortcuts land on manage modules', async ({ page }) => {
  await loginAsAdmin(page)

  await page.goto('/manage/ingestion')
  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('system-settings-page')).toBeVisible()

  await page.goto('/manage/admin/settings')
  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()

  await page.goto('/manage/master')
  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('admin-master-center')).toBeVisible()
  await expect(page.getByRole('heading', { name: '车间主数据' })).toBeVisible()

  await page.goto('/manage/admin/templates')
  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByTestId('template-editor-page')).toHaveCount(0)

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
  await expect(adminAside.locator('.xt-manage__nav-item.is-active', { hasText: /资料|基础资料/ })).toBeVisible()
  await expect(adminAside.getByRole('link', { name: /系统设置|设置/ })).toBeVisible()
  await expect(adminAside.getByRole('link', { name: /模板/ })).toHaveCount(0)
  await expect(adminAside.getByRole('link', { name: /导入/ })).toHaveCount(0)
  await expect(masterCenter.getByRole('heading', { name: '车间主数据' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '新增车间' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '编码' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '名称' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(masterCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('retired admin ingestion route redirects to system settings', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/ingestion')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByTestId('review-ingestion-center-v2')).toHaveCount(0)
})

test('admin settings route renders the system settings surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin/settings')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByRole('navigation', { name: '系统设置入口' })).toBeVisible()
  await expect(page.getByRole('link', { name: /用户管理/ })).toHaveAttribute('href', '/manage/admin/users')
  await expect(page.getByRole('link', { name: /QR 打印/ })).toHaveAttribute('href', '/manage/admin/qr-print')
  await expect(page.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('admin settings links to MES terminal binding management', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin/settings')

  const terminalLink = page.getByRole('link', { name: /终端绑定/ })
  await expect(terminalLink).toHaveAttribute('href', '/manage/mes-terminal-bindings')
  await terminalLink.click()

  await expect(page).toHaveURL(/\/manage\/mes-terminal-bindings$/)
  await expect(page.getByTestId('mes-terminal-binding-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'MES 终端绑定' })).toBeVisible()
  await expect(page.getByTestId('mes-terminal-binding-table')).toBeVisible()
})

test('admin settings route stays within viewport without overflow', async ({ page }) => {
  await loginAsAdmin(page)

  for (const viewport of [
    { width: 1366, height: 820 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/manage/admin/settings?desktop=1')

    await expect(page.getByTestId('system-settings-page')).toBeVisible()

    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth
    ))
    expect(overflow).toBeLessThanOrEqual(1)
  }
})

test('manage live route shows realtime process flow without page overflow', async ({ page }) => {
  await loginAsAdmin(page)
  await page.setViewportSize({ width: 1366, height: 820 })
  await page.goto('/manage/live')

  await expect(page.getByTestId('manage-live')).toBeVisible()
  await expect(page.getByText('生产流转总览')).toBeVisible()
  await expect(page.getByText('缺数据不计 0')).toBeVisible()
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('能耗采集')
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('物联网采集 · 09:20')
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('电工填报')
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('8,700 kWh')
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('41.31 kWh/吨')

  const overflow = await page.evaluate(() => Math.max(
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
    document.body.scrollWidth - document.body.clientWidth
  ))
  expect(overflow).toBeLessThanOrEqual(1)
})

test('manage live route stays readable on a narrow factory screen', async ({ page }) => {
  await loginAsAdmin(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/manage/live?desktop=1')

  await expect(page.getByTestId('manage-live')).toBeVisible()
  await expect(page.getByText('全厂实时调度墙')).toBeVisible()
  await expect(page.getByText('实时流转 / 机列矩阵 / 来源核验')).toBeVisible()
  await expect(page.getByText('生产流转总览')).toBeVisible()
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('能耗采集')

  const overflow = await page.evaluate(() => Math.max(
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
    document.body.scrollWidth - document.body.clientWidth
  ))
  expect(overflow).toBeLessThanOrEqual(1)
})

test('admin settings route does not render retired external missing input checklist', async ({ page }) => {
  await loginAsAdmin(page)

  for (const viewport of [
    { width: 1366, height: 820 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/manage/admin/settings?desktop=1')

    await expect(page.getByTestId('system-settings-page')).toBeVisible()
    await expect(page.locator('.external-readiness-missing')).toHaveCount(0)
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
  await loginAsFillOnlyOperator(page)

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
  await expect(page.getByTestId('system-settings-page')).toHaveCount(0)

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

  await page.goto('/manage/today')

  await expect(page).toHaveURL(/\/manage\/today$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  const manageSidebar = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  await expect(manageSidebar.getByRole('link', { name: /基础资料|资料/ })).toHaveCount(0)
  await expect(manageSidebar.getByRole('link', { name: /导入/ })).toHaveCount(0)
  await expect(manageSidebar.getByRole('link', { name: /系统设置|设置/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '管理端' })).toHaveCount(0)

  await page.goto('/manage/master')
  await expect(page).toHaveURL(/\/manage\/today$/)
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
  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await page.goto('/manage/today', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/manage\/today$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
})
