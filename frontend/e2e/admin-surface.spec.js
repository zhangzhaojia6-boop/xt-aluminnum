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
      super_admin_surface: true,
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

test('admin master route renders the master data smoke surface', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/master')

  const masterCenter = page.getByTestId('admin-master-center')
  const adminAside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')

  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByRole('button', { name: '设置' })).toHaveCount(0)
  await expect(adminAside.getByRole('link', { name: '主数据' })).toHaveAttribute('aria-current', 'page')
  await expect(adminAside.getByRole('link', { name: /模板/ })).toHaveCount(0)
  await expect(adminAside.getByRole('link', { name: /导入/ })).toHaveCount(0)
  await expect(masterCenter.getByRole('heading', { name: '车间主数据' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '新增车间' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '编码' })).toBeVisible()
  await expect(masterCenter.getByRole('columnheader', { name: '名称' })).toBeVisible()
  await expect(masterCenter.getByRole('button', { name: '提交生产数据' })).toHaveCount(0)
  await expect(masterCenter.getByRole('button', { name: '补录产量' })).toHaveCount(0)
})

test('manage live route shows realtime process flow without page overflow', async ({ page }) => {
  await loginAsAdmin(page)
  await page.setViewportSize({ width: 1366, height: 820 })
  await page.goto('/manage/live')

  await expect(page.getByTestId('manage-live')).toBeVisible()
  await expect(page.getByRole('region', { name: '生产流转总览' })).toBeVisible()
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
  await expect(page.getByLabel('实时流转 / 机列矩阵 / 来源核验')).toBeVisible()
  await expect(page.getByRole('region', { name: '生产流转总览' })).toBeVisible()
  await expect(page.getByTestId('stitch-bottom-status')).toContainText('能耗采集')

  const overflow = await page.evaluate(() => Math.max(
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
    document.body.scrollWidth - document.body.clientWidth
  ))
  expect(overflow).toBeLessThanOrEqual(1)
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
  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await page.goto('/manage/today', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/manage\/today$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
})

test('admin surface lands on master data and stays separate from entry surfaces', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto('/manage/admin')

  await expect(page).toHaveURL(/\/manage\/master$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('admin-master-center')).toBeVisible()
  await expect(page.getByText('现场填报')).toHaveCount(0)
  await expect(page.getByTestId('entry-shell')).toHaveCount(0)
})

test('retired settings and governance addresses land on the pages that replaced them', async ({ page }) => {
  await loginAsAdmin(page)

  for (const from of ['/manage/ingestion', '/manage/admin/settings', '/manage/admin/templates']) {
    await page.goto(from)
    await expect(page).toHaveURL(/\/manage\/master$/)
    await expect(page.getByTestId('admin-master-center')).toBeVisible()
  }

  await page.goto('/manage/admin/governance')
  await expect(page).toHaveURL(/\/manage\/admin\/users$/)

  await page.goto('/manage/attendance')
  await expect(page).toHaveURL(/\/manage\/today$/)
})

test('former settings entries live in collapsible left-nav groups', async ({ page }) => {
  await loginAsAdmin(page)
  await page.setViewportSize({ width: 1366, height: 820 })
  await page.goto('/manage/today')

  const aside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  await expect(aside.getByRole('button', { name: '配置' })).toHaveAttribute('aria-expanded', 'false')
  await expect(aside.getByRole('link', { name: 'PC 工艺映射' })).toHaveCount(0)

  await aside.getByRole('button', { name: '配置' }).click()
  const terminalLink = aside.getByRole('link', { name: 'PC 工艺映射' })
  await expect(terminalLink).toHaveAttribute('href', '/manage/mes-terminal-bindings')
  await terminalLink.click()

  await expect(page).toHaveURL(/\/manage\/mes-terminal-bindings$/)
  await expect(page.getByTestId('mes-terminal-binding-page')).toBeVisible()
  await expect(aside.getByRole('button', { name: '配置' })).toHaveAttribute('aria-expanded', 'true')
})

test('master data page stays within the viewport on desktop and phone', async ({ page }) => {
  await loginAsAdmin(page)

  for (const viewport of [
    { width: 1366, height: 820 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/manage/master?desktop=1')
    await expect(page.getByTestId('admin-master-center')).toBeVisible()

    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth
    ))
    expect(overflow).toBeLessThanOrEqual(1)
  }
})
