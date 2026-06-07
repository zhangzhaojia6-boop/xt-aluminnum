import { expect, test } from '@playwright/test'
import { clearAuthStorage } from './helpers/mock-login'

function fillUser(overrides = {}) {
  return {
    id: 21,
    username: 'playwright-entry-user',
    name: 'Playwright Entry User',
    role: 'machine_operator',
    is_mobile_user: true,
    is_reviewer: false,
    is_manager: false,
    data_scope_type: 'self_workshop',
    workshop_id: 2,
    assigned_shift_ids: [],
    ...overrides
  }
}

function machineInfo(overrides = {}) {
  return {
    machine_id: 21,
    machine_code: 'ZR2-1',
    machine_name: '1#机',
    workshop_id: 2,
    workshop_name: '铸二车间',
    qr_code: 'XT-ZR2-1',
    ...overrides
  }
}

async function mockMobileEntry(page, options = {}) {
  const workshopType = options.workshopType || 'casting'
  const machine = options.machine || null

  await page.route('**/api/v1/mobile/bootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'web_debug',
        current_identity_source: machine ? 'machine' : 'account',
        current_scope_summary: { data_scope_type: 'self_workshop' },
        workshop_id: 2,
        workshop_name: machine?.workshop_name || '铸二车间',
        workshop_type: workshopType,
        machine_id: machine?.machine_id || null,
        machine_code: machine?.machine_code || '',
        machine_name: machine?.machine_name || '',
        is_machine_bound: Boolean(machine)
      })
    })
  })

  await page.route('**/api/v1/mobile/current-shift', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-05-05',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 2,
        workshop_name: machine?.workshop_name || '铸二车间',
        workshop_type: workshopType,
        machine_id: machine?.machine_id || null,
        machine_code: machine?.machine_code || '',
        machine_name: machine?.machine_name || '',
        report_status: 'coil_entry',
        can_submit: true,
        is_machine_bound: Boolean(machine)
      })
    })
  })

  await page.route(`**/api/v1/templates/${workshopType}`, async (route) => {
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

test('dingtalk auth code inside redirect is consumed and stripped before entry landing', async ({ page }) => {
  let postedCode = ''
  await clearAuthStorage(page)
  await mockMobileEntry(page)
  await page.route('**/api/v1/dingtalk/h5-login', async (route) => {
    postedCode = route.request().postDataJSON().code
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'playwright-dingtalk-token',
        token_type: 'bearer',
        user: fillUser({ username: 'dingtalk-entry-user' }),
        machine_info: null
      })
    })
  })

  const redirect = encodeURIComponent('/entry?auth_code=dt-code&state=state-1&workshop=ZD')
  await page.goto(`/login?redirect=${redirect}`)

  await expect(page).toHaveURL(/\/entry\?workshop=ZD$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  expect(postedCode).toBe('dt-code')
})

test('machine qr query signs in and lands on the machine-bound entry surface', async ({ page }) => {
  const machine = machineInfo()
  let postedQr = ''
  await clearAuthStorage(page)
  await mockMobileEntry(page, { machine })
  await page.route('**/api/v1/auth/qr-login', async (route) => {
    postedQr = route.request().postDataJSON().qr_code
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'playwright-machine-token',
        token_type: 'bearer',
        user: fillUser({ username: 'machine-21' }),
        machine_info: machine
      })
    })
  })

  await page.goto('/login?machine=XT-ZR2-1')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('mobile-entry').getByText('1#机').first()).toBeVisible()
  expect(postedQr).toBe('XT-ZR2-1')
})

test('workshop director qr query signs in and lands on the workshop dashboard', async ({ page }) => {
  let postedQr = ''
  await clearAuthStorage(page)
  await page.route('**/api/v1/dashboard/workshop-director**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        target_date: '2026-06-07',
        workshop_id: 2,
        workshop_name: '铸二车间',
        total_output: 0,
        process_output: 0,
        pass_count_total: 0
      })
    })
  })
  await page.route('**/api/v1/aggregation/live?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workshops: [{ workshop_id: 2, workshop_name: '铸二车间' }],
        overall_progress: {},
        quality: {},
        mes_machine_binding: {}
      })
    })
  })
  await page.route('**/api/v1/aggregation/live/fill-details**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/aggregation/live/pending-assignment**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: { entry_count: 0 } }) })
  })
  await page.route('**/api/v1/mes/extended/workshop-process-records**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })
  await page.route('**/api/v1/mes/extended/material-records**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })
  await page.route('**/api/v1/auth/qr-login', async (route) => {
    postedQr = route.request().postDataJSON().qr_code
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'playwright-director-token',
        token_type: 'bearer',
        user: fillUser({
          username: 'ZR2-DIR',
          name: '铸二车间主任',
          role: 'workshop_director',
          is_mobile_user: false,
          is_reviewer: true,
          is_manager: true,
          data_scope_type: 'self_workshop',
        }),
        machine_info: null
      })
    })
  })

  await page.goto('/login?machine=XT-ZR2-DIR')

  await expect(page).toHaveURL(/\/manage\/workshop-dashboard/)
  await expect(page.getByTestId('workshop-dashboard-page')).toBeVisible()
  expect(postedQr).toBe('XT-ZR2-DIR')
})

test('workshop qr result and workshop query keep users on login with workshop hint', async ({ page }) => {
  let postedQr = ''
  await clearAuthStorage(page)
  await page.route('**/api/v1/auth/qr-login', async (route) => {
    postedQr = route.request().postDataJSON().qr_code
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'workshop_redirect',
        workshop_code: 'ZD',
        workshop_name: '铸锭车间'
      })
    })
  })

  await page.goto('/login?machine=WORKSHOP-ZD')

  await expect(page).toHaveURL(/\/login\?machine=WORKSHOP-ZD$/)
  await expect(page.getByTestId('login-page')).toBeVisible()
  await expect(page.getByText('车间：铸锭车间，请用该车间的角色账号登录')).toBeVisible()
  expect(postedQr).toBe('WORKSHOP-ZD')

  await page.goto('/login?workshop=JZ')

  await expect(page.getByTestId('login-page')).toBeVisible()
  await expect(page.getByText('车间：JZ，请用该车间的角色账号登录')).toBeVisible()
})
