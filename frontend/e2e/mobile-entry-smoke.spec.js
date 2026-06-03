import { expect, test } from '@playwright/test'
import { clearAuthStorage } from './helpers/mock-login'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'
import { firstEnv, skipWithoutCredentials } from './helpers/credentials'

const username = firstEnv('PLAYWRIGHT_USERNAME', 'INIT_ADMIN_USERNAME')
const password = firstEnv('PLAYWRIGHT_PASSWORD', 'INIT_ADMIN_PASSWORD')
const responsiveWidths = [375, 390, 414, 768]

async function seedStoredSession(page, token, user, machineContext = null) {
  await page.addInitScript(({ token, user, machineContext }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    if (machineContext) {
      localStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
      sessionStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
    } else {
      localStorage.removeItem('aluminum_bypass_machine')
      sessionStorage.removeItem('aluminum_bypass_machine')
    }
  }, { token, user, machineContext })
}

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

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user)
    })
  })

  await page.route('**/api/v1/mobile/bootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'web_debug',
        current_identity_source: 'account',
        current_scope_summary: { data_scope_type: 'self_team' },
        workshop_id: 1,
        workshop_name: '挤压车间',
        workshop_type: 'extrusion',
        is_machine_bound: false
      })
    })
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

  await page.route('**/api/v1/templates/extrusion', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        supports_ocr: false,
        role_bucket: 'operator',
        entry_fields: [],
        shift_fields: [],
        extra_fields: [],
        qc_fields: [],
        readonly_fields: []
      })
    })
  })
}

async function setupUnifiedPerCoilEntrySession(page) {
  const token = 'playwright-coil-token'
  const user = {
    id: 21,
    username: 'machine-21',
    name: '铸二车间 1#机',
    role: 'machine_operator',
    is_mobile_user: true,
    is_reviewer: false,
    is_manager: false,
    data_scope_type: 'self_workshop',
    workshop_id: 2,
    assigned_shift_ids: []
  }
  const machineContext = {
    machine_id: 21,
    machine_code: 'ZR2-1',
    machine_name: '1#机',
    workshop_id: 2,
    workshop_name: '铸二车间',
    qr_code: 'XT-ZR2-1'
  }
  await seedStoredSession(page, token, user, machineContext)

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user)
    })
  })

  await page.route('**/api/v1/mobile/bootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'web_debug',
        current_identity_source: 'machine',
        current_scope_summary: { data_scope_type: 'self_workshop' },
        workshop_id: 2,
        workshop_name: '铸二车间',
        workshop_type: 'casting',
        machine_id: 21,
        machine_code: 'ZR2-1',
        machine_name: '1#机',
        is_machine_bound: true
      })
    })
  })

  await page.route('**/api/v1/mobile/current-shift', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-05-01',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 2,
        workshop_name: '铸二车间',
        workshop_type: 'casting',
        machine_id: 21,
        machine_code: 'ZR2-1',
        machine_name: '1#机',
        report_status: 'coil_entry',
        can_submit: true,
        is_machine_bound: true
      })
    })
  })

  await page.route('**/api/v1/templates/casting', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        supports_ocr: false,
        role_bucket: 'operator',
        entry_fields: [],
        shift_fields: [],
        extra_fields: [],
        qc_fields: [],
        readonly_fields: []
      })
    })
  })

  await page.route('**/api/v1/mobile/entry-fields', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        mode: 'per_coil',
        submit_target: 'coil_entry',
        identity_field: 'tracking_card_no',
        role: 'machine_operator',
        role_label: '产量数据',
        groups: [{
          label: '产量数据',
          fields: [
            { name: 'tracking_card_no', label: '随行卡号', type: 'text', required: true },
            { name: 'alloy_grade', label: '合金', type: 'text', required: true },
            { name: 'input_weight', label: '投入重量', type: 'number', unit: 'kg', required: true },
            { name: 'output_weight', label: '产出重量', type: 'number', unit: 'kg', required: true }
          ]
        }],
        readonly_fields: []
      })
    })
  })

  await page.route('**/api/v1/mobile/coil-list/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([])
    })
  })

  await page.route('**/api/v1/mobile/coil-entry', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.tracking_card_no).toBe('TC-001')
    expect(body.input_weight).toBe(100)
    expect(body.output_weight).toBe(96)
    expect(body.data).toBeUndefined()
    expect(body.extra_payload?.quality_issue).toBeUndefined()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        tracking_card_no: body.tracking_card_no,
        alloy_grade: body.alloy_grade,
        input_weight: body.input_weight,
        output_weight: body.output_weight,
        scrap_weight: body.scrap_weight || 0,
        business_date: body.business_date
      })
    })
  })
}

test('admin mobile entry shows the manual-first mobile entry', async ({ page }) => {
  skipWithoutCredentials([
    ['PLAYWRIGHT_USERNAME or INIT_ADMIN_USERNAME', username],
    ['PLAYWRIGHT_PASSWORD or INIT_ADMIN_PASSWORD', password]
  ])

  await clearAuthStorage(page)
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(?:entry|manage\/today|manage\/admin(?:\/settings)?)$/)

  if (!page.url().endsWith('/entry')) {
    const currentShiftResponse = page.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/current-shift') &&
      response.request().method() === 'GET'
    )
    await page.goto('/entry')
    await currentShiftResponse
  }

  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByRole('heading', { name: '录产量' })).toBeVisible()
  const entryState = await Promise.race([
    page.getByText('当前账号暂未拿到可显示的班次任务。').waitFor({ state: 'visible' }).then(() => 'empty'),
    page.getByTestId('mobile-current-shift').waitFor({ state: 'visible' }).then(() => 'current')
  ])
  if (entryState === 'empty') {
    await expect(page.getByRole('button', { name: '刷新任务' })).toBeVisible()
    await expect(page.getByTestId('mobile-go-report')).toHaveCount(0)
  } else {
    await expect(page.getByTestId('mobile-go-report')).toBeVisible()
  }
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
    await expect(page.getByRole('heading', { name: '录产量' })).toBeVisible()
    await expect(page.getByText('按卷记录投入、产出重量')).toBeVisible()
    await expect(page.getByRole('button', { name: '开始填报' })).toBeVisible()
    await expect(entryShell.getByRole('link', { name: /草稿/ })).toBeVisible()
    await expect(entryShell.getByText('管理端')).toHaveCount(0)
    await expect(entryShell.getByText('审阅端')).toHaveCount(0)
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, entryShell)
  })
}

test('fill-only operator lands on entry and cannot see review or admin navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupFillOnlyEntrySession(page)

  await page.goto('/manage/ai')

  const entryShell = page.getByTestId('entry-shell')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(entryShell).toBeVisible()
  await expect(entryShell.getByText('管理端')).toHaveCount(0)
  await expect(entryShell.getByText('审阅端')).toHaveCount(0)
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
})

test('machine entry keeps quality detail fields collapsed until issue is enabled', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupUnifiedPerCoilEntrySession(page)

  await page.goto('/entry/fill')

  const qualityModule = page.getByTestId('quality-module')
  await expect(qualityModule).toBeVisible()
  await expect(qualityModule.getByText('有填报问题')).toBeVisible()
  await expect(qualityModule.getByText('问题类型')).toHaveCount(0)
  await expect(qualityModule.getByText('问题描述')).toHaveCount(0)
  await expect(qualityModule.getByText('现场照片')).toHaveCount(0)

  await qualityModule.locator('.el-switch').click()

  await expect(qualityModule.getByText('问题类型')).toBeVisible()
  await expect(qualityModule.getByText('问题描述')).toBeVisible()
  await expect(qualityModule.getByText('现场照片')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectContainerInsideViewport(page, page.getByTestId('unified-entry'))
})

test('entry history loads all-day records instead of only the current shift', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupFillOnlyEntrySession(page)
  const historyRequests = []

  await page.route('**/api/v1/mobile/report/history**', async (route) => {
    const url = new URL(route.request().url())
    historyRequests.push(Object.fromEntries(url.searchParams.entries()))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 101,
            source_type: 'shift_report',
            business_date: '2026-05-30',
            shift_id: 1,
            shift_name: '大夜班',
            workshop_name: '退火一车间',
            team_name: '大夜班',
            output_weight: 8.6,
            report_status: 'submitted',
            created_by_name: '张师傅',
            last_saved_at: '2026-05-30 07:40'
          },
          {
            id: 202,
            source_type: 'mobile_coil',
            role_bucket: 'machine_operator',
            business_date: '2026-05-30',
            shift_id: 2,
            shift_name: '长白班',
            workshop_name: '退火一车间',
            machine_name: '2050# 主操',
            tracking_card_no: 'TX-20260530-001',
            input_weight: 9.8,
            output_weight: 9.4,
            scrap_weight: 0.4,
            report_status: 'submitted',
            created_by_name: '李师傅',
            last_saved_at: '2026-05-30 12:10'
          }
        ]
      })
    })
  })

  await page.goto('/entry/history')

  await expect(page.getByTestId('entry-history-page')).toBeVisible()
  const records = page.getByTestId('entry-history-record')
  await expect(records).toHaveCount(2)
  await expect(records.nth(0)).toContainText('大夜班')
  await expect(records.nth(1)).toContainText('长白班')
  await expect(records.nth(1)).toContainText('主操逐卷')
  await expect(records.nth(1)).toContainText('TX-20260530-001')
  await expect.poll(() => historyRequests[0]?.all_day).toBe('true')
  expect(historyRequests[0]).not.toHaveProperty('shift_id')
  await expectNoHorizontalOverflow(page)
  await expectContainerInsideViewport(page, page.getByTestId('entry-shell'))
})

test('unified per-coil entry submits top-level payload without false required failure', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupUnifiedPerCoilEntrySession(page)

  await page.goto('/entry/fill')
  await page.getByLabel('随行卡号').fill('TC-001')
  await page.getByLabel('合金').fill('5052')
  await page.getByLabel(/投入重量/).fill('100')
  await page.getByLabel(/产出重量/).fill('96')
  await page.getByRole('button', { name: '录入本卷' }).click()

  await expect(page.getByText('第1卷 录入成功')).toBeVisible()
  await expect(page.getByText(/required|必填项未填写/i)).toHaveCount(0)
})

for (const width of responsiveWidths) {
  test(`machine unified entry route stays inside ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width >= 768 ? 1024 : 844 })
    await setupUnifiedPerCoilEntrySession(page)

    await page.goto('/entry/fill')
    await expect(page).toHaveURL(/\/entry\/fill$/)
    await expect(page.getByTestId('unified-entry')).toBeVisible()
    await expect(page.getByLabel('随行卡号')).toBeVisible()
    await expect(page.getByTestId('entry-mes-trace-card')).toHaveCount(0)
    await expect(page.getByText('外部系统线索')).toHaveCount(0)
    await expect(page.getByText('不补后续码')).toHaveCount(0)
    await expect(page.getByText(/MES 后续码.*必填/)).toHaveCount(0)
    await expect(page.getByRole('button', { name: '录入本卷' })).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('unified-entry'))

    await page.goto('/entry')
    await expect(page).toHaveURL(/\/entry$/)
    await expect(page.getByTestId('mobile-entry')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await expectContainerInsideViewport(page, page.getByTestId('entry-shell'))
  })
}
