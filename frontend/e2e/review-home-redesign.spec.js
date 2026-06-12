import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'
import { loginThroughMockedPassword } from './helpers/mock-login'

const workshopDirectorUser = {
  id: 8,
  username: 'workshop-director',
  name: '车间主任',
  role: 'workshop_director',
  workshop_id: 1,
  is_mobile_user: true,
  is_reviewer: true,
  is_manager: true,
  data_scope_type: 'self_workshop',
  assigned_shift_ids: []
}

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

async function expectNoHorizontalOverflow(page) {
  await expect.poll(async () => {
    try {
      return await page.evaluate(() => {
        const root = document.scrollingElement || document.documentElement
        return Math.max(root.scrollWidth, document.body.scrollWidth) - window.innerWidth
      })
    } catch {
      return Number.POSITIVE_INFINITY
    }
  }).toBeLessThanOrEqual(2)
}

async function expectManageChrome(page) {
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  if ((page.viewportSize()?.width || 0) <= 900) {
    await expect(page.locator('.xt-manage__hamburger')).toBeVisible()
  } else {
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
  }
  await expectNoHorizontalOverflow(page)
}

test('manage shell keeps the production surface readable on desktop widths', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/manage/production')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()
})

test('compact management clients keep core review routes with desktop override', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })

  await page.goto('/manage/live')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-live')).toBeVisible()

  await page.goto('/manage/today')
  await expectManageChrome(page)
  await expect(page.getByTestId('manage-today')).toBeVisible()

  for (const [path, testId] of [
    ['/manage/production', 'manage-production'],
    ['/manage/fill-details', 'manage-fill-details']
  ]) {
    await page.goto(`${path}?desktop=1`)
    await expectManageChrome(page)
    await expect(page).toHaveURL(new RegExp(path.replace('/', '\\/')))
    await expect(page.getByTestId(testId)).toBeVisible()
  }

  await page.goto('/manage/daily-report?desktop=1')
  await expectManageChrome(page)
  await expect(page).toHaveURL(/\/manage\/today/)
  await expect(page.getByTestId('manage-today')).toBeVisible()
})

test('compact workshop director clients only keep own workshop dashboard route', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 })
  await page.unroute('**/api/v1/auth/me')
  await page.unroute('**/api/v1/auth/login')
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(workshopDirectorUser)
    })
  })
  await loginThroughMockedPassword(page, {
    token: 'playwright-workshop-director-token',
    user: workshopDirectorUser
  })

  await expectManageChrome(page)
  await expect(page).toHaveURL(/\/manage\/workshop-dashboard/)
  await expect(page.getByTestId('workshop-dashboard-page')).toBeVisible()
  await expect(page.getByTestId('workshop-dashboard-filter')).toHaveCount(0)
  await page.waitForLoadState('networkidle')

  await page.locator('.xt-manage__hamburger').click()
  const drawerNav = page.locator('.xt-manage__drawer-nav')
  await expect(drawerNav).toBeVisible()
  const drawerItems = drawerNav.locator('a.xt-manage__nav-item')
  await expect(drawerItems).toHaveCount(1)
  await expect(drawerItems.first()).toContainText('车间看板')
  await page.keyboard.press('Escape')

  for (const path of ['/manage/live', '/manage/today', '/manage/production', '/manage/fill-details', '/manage/admin/settings']) {
    await page.goto(`${path}?desktop=1`)
    await expectManageChrome(page)
    await expect(page).toHaveURL(/\/manage\/workshop-dashboard/)
    await expect(page.getByTestId('workshop-dashboard-page')).toBeVisible()
  }
})

test('manage shell keeps current core centers readable on tablet and mobile widths', async ({ page }) => {
  const centers = [
    { path: '/manage/today', testId: 'manage-today' },
    { path: '/manage/production', testId: 'manage-production' },
    { path: '/manage/fill-details', testId: 'manage-fill-details' },
    { path: '/manage/admin/settings', testId: 'system-settings-page' }
  ]

  await page.setViewportSize({ width: 1100, height: 900 })

  for (const center of centers) {
    await page.goto(center.path)
    await expectManageChrome(page)
    await expect(page.getByTestId(center.testId)).toBeVisible()
  }
})

test('production center exposes current production board and summary sections', async ({ page }) => {
  await page.goto('/manage/production')

  await expectManageChrome(page)
  await expect(page.getByTestId('manage-production')).toBeVisible()
  await expect(page.getByRole('heading', { name: '生产', exact: true })).toBeVisible()
  await expect(page.getByText('车间产量排名')).toBeVisible()
  await expect(page.getByText('生产摘要')).toBeVisible()
})
