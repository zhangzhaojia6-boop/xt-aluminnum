import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong'
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

async function writeStoredSession(page, token, user, machineContext = null) {
  await page.evaluate(({ token, user, machineContext }) => {
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
  await setupReviewSessionAndMocks(page, { token, user })
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

  await page.goto('/login')
  await writeStoredSession(page, token, user, machineContext)
}

test('admin mobile entry shows the manual-first mobile fallback entry', async ({ page }) => {
  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/manage\/(overview|admin)$/)

  const currentShiftResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/mobile/current-shift') &&
    response.request().method() === 'GET'
  )
  await page.goto('/entry')
  await currentShiftResponse

  const currentShiftCard = page.getByTestId('mobile-current-shift')

  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(currentShiftCard).toBeVisible()
  await expect(page.getByRole('heading', { name: '录产量' })).toBeVisible()
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
    await expect(page.getByRole('heading', { name: '录产量' })).toBeVisible()
    await expect(page.getByText('记录本班次生产数据')).toBeVisible()
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
