import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'
const responsiveWidths = [375, 390, 414, 768]

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const root = document.documentElement
    const scrollingElement = document.scrollingElement || root
    return {
      clientWidth: root.clientWidth,
      windowWidth: window.innerWidth,
      documentWidth: scrollingElement.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }
  })
  const viewportWidth = overflow.clientWidth || overflow.windowWidth
  expect(overflow.documentWidth).toBeLessThanOrEqual(viewportWidth + 2)
  expect(overflow.bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

async function expectContainerInsideViewport(page, locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  const viewportWidth = page.viewportSize()?.width || 0
  expect(box.x).toBeGreaterThanOrEqual(-2)
  expect(box.x + box.width).toBeLessThanOrEqual(viewportWidth + 2)
}

async function setupFillOnlyEntrySession(page) {
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

  await page.route('**/api/v1/mobile/current-shift', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-04-23',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '挤压车间',
        workshop_type: 'extrusion',
        can_submit: true,
        is_machine_bound: false
      })
    })
  })
}

test('admin mobile entry shows the manual-first mobile fallback entry', async ({ page }) => {
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/review\/(factory|overview)/)

  const currentShiftResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/current-shift') &&
    response.request().method() === 'GET'
  )
  await page.goto('/mobile')
  await currentShiftResponse

  const currentShiftCard = page.getByTestId('mobile-current-shift')

  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(currentShiftCard).toBeVisible()
  await expect(page.getByTestId('mobile-role-bucket')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()
  await expect(page.getByRole('button', { name: '打开审阅端' })).toHaveCount(0)
  await expect(page.getByText('采集清洗小队')).toHaveCount(0)
  await expect(page.getByText('分析决策小队')).toHaveCount(0)
})

for (const width of responsiveWidths) {
  test(`entry home stays inside ${width}px and keeps operator-only copy`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await setupFillOnlyEntrySession(page)

    await page.goto('/entry')

    const entryShell = page.getByTestId('entry-shell')
    await expect(page).toHaveURL(/\/entry$/)
    await expect(entryShell).toBeVisible()
    await expect(page.getByTestId('mobile-entry')).toBeVisible()
    await expect(page.getByRole('heading', { name: '今日任务' })).toBeVisible()
    await expect(page.getByRole('button', { name: /开始填报/ })).toBeVisible()
    await expect(entryShell.getByRole('button', { name: '草稿箱', exact: true })).toBeVisible()
    await expect(entryShell.getByRole('button', { name: '历史记录', exact: true })).toBeVisible()
    await expect(entryShell.getByText('管理端')).toHaveCount(0)
    await expect(entryShell.getByText('审阅端')).toHaveCount(0)
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, entryShell)
  })
}

test('fill-only operator lands on entry and cannot see review or admin navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupFillOnlyEntrySession(page)

  await page.goto('/review/brain')

  const entryShell = page.getByTestId('entry-shell')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(entryShell).toBeVisible()
  await expect(entryShell.getByText('管理端')).toHaveCount(0)
  await expect(entryShell.getByText('审阅端')).toHaveCount(0)
  await expect(page.getByTestId('review-shell')).toHaveCount(0)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
})

for (const width of responsiveWidths) {
  test(`machine entry report and advanced routes stay inside ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width >= 768 ? 1024 : 844 })
    await page.goto('/login?machine=XT-ZD-1')

    await expect(page).toHaveURL(/\/(mobile|entry)$/)
    await expect(page.getByTestId('mobile-go-report')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('entry-shell'))

    await page.getByTestId('mobile-go-report').click()
    await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)
    await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
    await expect(page.getByText('线索追踪（待 MES 对接确认）')).toBeVisible()
    await expect(page.getByText('当前不要求主操填写 MES 后续码。')).toBeVisible()
    await expect(page.getByText(/MES 后续码.*必填/)).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存草稿' })).toBeVisible()
    await expect(page.getByRole('button', { name: '下一步' })).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('dynamic-entry-form'))

    const match = page.url().match(/\/entry\/advanced\/([^/]+)\/([^/?#]+)/)
    expect(match).not.toBeNull()
    await page.goto(`/entry/report/${match[1]}/${match[2]}`)
    await expect(page.getByTestId('mobile-shift-report-workspace')).toBeVisible()
    await expect(page.getByRole('button', { name: '保存草稿' })).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('mobile-shift-report-workspace'))

    await page.goto('/mobile')
    await expect(page).toHaveURL(/\/entry$/)
    await expect(page.getByTestId('mobile-entry')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('entry-shell'))
  })
}
