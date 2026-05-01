import { expect, test } from '@playwright/test'

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'https://127.0.0.1'

const adminUser = {
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

const machineUser = {
  id: 21,
  username: 'XT-ZD-1',
  name: '铸轧一车间 1#机',
  role: 'machine_operator',
  is_mobile_user: true,
  is_reviewer: false,
  is_manager: false,
  data_scope_type: 'self_workshop',
  workshop_id: 1,
  assigned_shift_ids: []
}

function seedSession(target, { token, user, machine = null }) {
  return target.addInitScript(({ token, user, machine }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    if (machine) {
      localStorage.setItem('aluminum_bypass_machine', JSON.stringify(machine))
      sessionStorage.setItem('aluminum_bypass_machine', JSON.stringify(machine))
    } else {
      localStorage.removeItem('aluminum_bypass_machine')
      sessionStorage.removeItem('aluminum_bypass_machine')
    }
  }, { token, user, machine })
}

function fulfillJson(route, payload) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload)
  })
}

test('admin can save workshop template fields and machine user consumes the updated template', async ({ page }) => {
  const fieldName = `qa_entry_${Date.now()}`
  const fieldLabel = `测试字段${Date.now()}`
  let template = {
    template_key: 'ZD',
    workshop_type: 'casting',
    source_template_key: 'casting',
    has_override: false,
    display_name: '铸轧一车间模板',
    tempo: 'slow',
    supports_ocr: false,
    entry_fields: [
      { name: 'alloy_grade', label: '合金牌号', type: 'text', unit: '', hint: '', compute: '', required: true, enabled: true },
      { name: 'input_weight', label: '投入重量', type: 'number', unit: 'kg', hint: '', compute: '', required: true, enabled: true },
      { name: 'output_weight', label: '产出重量', type: 'number', unit: 'kg', hint: '', compute: '', required: true, enabled: true }
    ],
    shift_fields: [],
    extra_fields: [],
    qc_fields: [],
    readonly_fields: []
  }

  await seedSession(page, { token: 'playwright-admin-token', user: adminUser })
  await page.route('**/api/v1/auth/me', (route) => fulfillJson(route, adminUser))
  await page.route('**/api/v1/master/workshops**', (route) => fulfillJson(route, {
    items: [
      { id: 1, code: 'ZD', name: '铸轧一车间', workshop_code: 'ZD', workshop_name: '铸轧一车间', workshop_type: 'casting', is_active: true, sort_order: 1 }
    ],
    total: 1
  }))
  await page.route(/.*\/api\/v1\/master\/workshop-templates\/ZD$/, async (route) => {
    if (route.request().method() === 'PUT') {
      template = {
        ...template,
        ...route.request().postDataJSON(),
        template_key: 'ZD',
        workshop_type: 'casting',
        source_template_key: 'ZD',
        has_override: true
      }
    }
    await fulfillJson(route, template)
  })

  await page.goto('/manage/admin/templates')
  await expect(page.getByTestId('template-editor-page')).toBeVisible()
  await expect(page.getByTestId('template-entry_fields-name-0')).toHaveValue('alloy_grade')

  const nextIndex = template.entry_fields.length
  await page.getByTestId('template-add-entry_fields').click()
  await page.getByTestId(`template-entry_fields-name-${nextIndex}`).fill(fieldName)
  await page.getByTestId(`template-entry_fields-label-${nextIndex}`).fill(fieldLabel)

  const saveResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/master/workshop-templates/ZD') &&
    response.request().method() === 'PUT'
  )
  await page.getByTestId('template-save').click()
  expect((await saveResponse).ok()).toBeTruthy()
  expect(template.entry_fields.some((field) => field.name === fieldName && field.label === fieldLabel)).toBeTruthy()

  const browser = page.context().browser()
  const machineContext = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 430, height: 932 },
    isMobile: true,
    hasTouch: true
  })
  await seedSession(machineContext, {
    token: 'playwright-machine-token',
    user: machineUser,
    machine: {
      machine_id: 21,
      machine_code: 'ZD-1',
      machine_name: '1#机',
      workshop_id: 1,
      workshop_name: '铸轧一车间',
      qr_code: 'XT-ZD-1'
    }
  })
  const machinePage = await machineContext.newPage()

  await machinePage.route('**/api/v1/auth/me', (route) => fulfillJson(route, machineUser))
  await machinePage.route('**/api/v1/mobile/bootstrap', (route) => fulfillJson(route, {
    entry_mode: 'web_debug',
    current_identity_source: 'account',
    current_scope_summary: { data_scope_type: 'self_workshop' },
    workshop_id: 1,
    workshop_code: 'ZD',
    workshop_name: '铸轧一车间',
    workshop_type: 'casting',
    machine_id: 21,
    machine_code: 'ZD-1',
    machine_name: '1#机',
    is_machine_bound: true,
    user_role: 'machine_operator'
  }))
  await machinePage.route('**/api/v1/mobile/current-shift', (route) => fulfillJson(route, {
    business_date: '2026-05-01',
    shift_id: 1,
    shift_name: '白班',
    workshop_id: 1,
    workshop_code: 'ZD',
    workshop_name: '铸轧一车间',
    workshop_type: 'casting',
    machine_id: 21,
    machine_code: 'ZD-1',
    machine_name: '1#机',
    report_status: 'coil_entry',
    can_submit: true,
    is_machine_bound: true
  }))
  await machinePage.route('**/api/v1/templates/ZD', (route) => fulfillJson(route, template))
  await machinePage.route('**/api/v1/mobile/entry-fields', (route) => fulfillJson(route, {
    mode: 'per_coil',
    submit_target: 'coil_entry',
    identity_field: 'tracking_card_no',
    role: 'machine_operator',
    role_label: '产量数据',
    groups: [{
      label: '产量数据',
      fields: [
        { name: 'tracking_card_no', label: '随行卡号', type: 'text', required: true },
        ...template.entry_fields
      ]
    }],
    readonly_fields: []
  }))
  await machinePage.route('**/api/v1/mobile/coil-list/**', (route) => fulfillJson(route, []))

  try {
    await machinePage.goto(`${baseURL}/entry`)
    await expect(machinePage.getByTestId('mobile-entry')).toBeVisible()
    await machinePage.getByTestId('mobile-go-report').click()
    await expect(machinePage).toHaveURL(/\/entry\/fill$/)
    await expect(machinePage.getByTestId('unified-entry')).toBeVisible()
    await expect(machinePage.getByTestId(`field-${fieldName}`)).toContainText(fieldLabel)
  } finally {
    await machineContext.close()
  }
})
