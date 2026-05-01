import { expect } from '@playwright/test'

export async function setupUnifiedPerCoilEntrySession(page, options = {}) {
  const trackingCard = options.trackingCard || 'TC-001'
  const inputWeight = options.inputWeight ?? 100
  const outputWeight = options.outputWeight ?? 96
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

  await page.addInitScript(({ token, user, machineContext }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    localStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
  }, { token, user, machineContext })

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
        current_scope_summary: { data_scope_type: 'self_workshop' },
        workshop_id: 2,
        workshop_name: '铸二车间',
        workshop_type: 'casting',
        machine_id: 21,
        machine_code: 'ZR2-1',
        machine_name: '1#机',
        is_machine_bound: true,
        user_role: 'machine_operator'
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

  await page.route('**/api/v1/templates/casting', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        supports_ocr: false,
        role_bucket: 'machine_operator',
        entry_fields: [],
        shift_fields: [],
        extra_fields: [],
        qc_fields: [],
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
    expect(body.tracking_card_no).toBe(trackingCard)
    expect(body.input_weight).toBe(inputWeight)
    expect(body.output_weight).toBe(outputWeight)
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
  await page.evaluate(({ token, user, machineContext }) => {
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    localStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
    sessionStorage.setItem('aluminum_bypass_machine', JSON.stringify(machineContext))
  }, { token, user, machineContext })
}
