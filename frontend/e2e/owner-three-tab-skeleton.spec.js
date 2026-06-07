import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

async function gotoRedirectingManagePath(page, path, expectedUrl) {
  await page.goto(path).catch((error) => {
    if (!String(error).includes('interrupted by another navigation')) throw error
  })
  await expect(page).toHaveURL(expectedUrl)
}

test.describe('owner three-tab skeleton', () => {
  test.beforeEach(async ({ page }) => {
    await setupReviewSessionAndMocks(page)
  })

  test('today tab renders with the current management navigation groups', async ({ page }) => {
    await page.goto('/manage/today')

    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByRole('heading', { name: '工厂总览' })).toBeVisible()
    await expect(page.locator('.xt-manage__sidebar .xt-manage__nav-group-label')).toHaveText([
      '实时调度',
      '昨日报表',
      '生产分析',
      '人员考勤',
      '系统'
    ])
  })

  test('navigates the core management tabs without 404', async ({ page }) => {
    await page.goto('/manage/today')
    await expect(page.getByTestId('manage-today')).toBeVisible()
    const sidebarNav = page.getByRole('navigation', { name: '管理端导航' })

    const productionLink = sidebarNav.getByRole('link', { name: '生产分析', exact: true })
    await expect(productionLink).toHaveAttribute('href', '/manage/production')
    await productionLink.click({ force: true })
    await expect(page).toHaveURL(/\/manage\/production$/)
    await expect(page.getByTestId('manage-production')).toBeVisible()

    const alertsLink = sidebarNav.getByRole('link', { name: '异常处理', exact: true })
    await expect(alertsLink).toHaveAttribute('href', '/manage/alerts')
    await alertsLink.click({ force: true })
    await expect(page).toHaveURL(/\/manage\/alerts$/)
    await expect(page.getByTestId('manage-alerts')).toBeVisible()

    const todayLink = sidebarNav.getByRole('link', { name: '昨日报表', exact: true })
    await expect(todayLink).toHaveAttribute('href', '/manage/today')
    await todayLink.click({ force: true })
    await expect(page).toHaveURL(/\/manage\/today$/)
    await expect(page.getByTestId('manage-today')).toBeVisible()
  })

  test('legacy management paths redirect into the owner skeleton', async ({ page }) => {
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/manage\/today$/)

    await gotoRedirectingManagePath(page, '/manage/factory', /\/manage\/today$/)

    await gotoRedirectingManagePath(page, '/manage/quality', /\/manage\/alerts(?:\?domain=quality)?$/)
  })

  test('settings drawer exposes frozen destinations and routes to the page', async ({ page }) => {
    await page.goto('/manage/today', { waitUntil: 'networkidle' })
    await expect(page.getByTestId('manage-today')).toBeVisible()

    await page.locator('.xt-manage__settings-trigger').click()

    const settingsNav = page.getByRole('navigation', { name: '管理端设置' })
    await expect(settingsNav).toBeVisible()
    await expect(settingsNav.getByText('杂项 (冻结)')).toBeVisible()

    const destinationLink = settingsNav.getByRole('link', { name: /库存去向/ })
    await expect(destinationLink).toHaveAttribute('href', '/manage/factory/destinations')
    await destinationLink.click({ force: true })

    await expect(page).toHaveURL(/\/manage\/factory\/destinations$/)
  })
})
