import { expect, test } from '@playwright/test'

test('mobile coil entry scans a coil qr and submits editable header fields', async ({ page }) => {
  let submitPayload = null

  await page.addInitScript(() => {
    sessionStorage.setItem('aluminum_bypass_token', 'scan-token')
    sessionStorage.setItem(
      'aluminum_bypass_user',
      JSON.stringify({
        id: 8,
        username: 'operator',
        name: '主操',
        role: 'machine_operator',
        workshop_id: 1,
        team_id: 10,
        data_scope_type: 'self_workshop',
        is_mobile_user: true,
        is_reviewer: false,
        is_manager: false
      })
    )
    window.dd = {
      biz: {
        util: {
          scan({ onSuccess }) {
            onSuccess({ text: 'QR-SCAN-1' })
          }
        }
      }
    }
  })

  await page.route('**/api/v1/mobile/bootstrap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'dingtalk_h5',
        dingtalk_enabled: true,
        user_has_dingtalk_binding: true,
        current_identity_source: 'dingtalk_oauth',
        current_scope_summary: { data_scope_type: 'self_workshop' },
        workshop_id: 1,
        workshop_name: '铸二车间',
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
        business_date: '2026-05-03',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '铸二车间',
        machine_id: 21,
        machine_code: 'ZR2-1',
        machine_name: '1#机',
        report_status: 'pending',
        can_submit: true,
        is_machine_bound: true
      })
    })
  })

  await page.route('**/api/v1/mobile/coil-list/2026-05-03/1', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })

  await page.route('**/api/v1/mobile/coil-flow-suggestion?**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })

  await page.route('**/api/v1/mobile/scan-lookup?**', async (route) => {
    expect(route.request().url()).toContain('qr=QR-SCAN-1')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source: 'coil_snapshot',
        header_fields: {
          tracking_card_no: 'TRACK-SCAN-1',
          alloy_grade: '6061',
          input_spec: '1.2×1200',
          current_workshop: '冷轧车间',
          current_process: '冷轧',
          next_workshop: '退火车间',
          next_process: '退火'
        },
        lock_keys: [],
        lock_token: null
      })
    })
  })

  await page.route('**/api/v1/mobile/coil-entry', async (route) => {
    submitPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        tracking_card_no: 'TRACK-SCAN-1',
        alloy_grade: '6061',
        input_spec: '1.2×1200',
        input_weight: 1000,
        output_weight: 960,
        scrap_weight: 40,
        operator_notes: '',
        extra_payload: {},
        business_date: '2026-05-03'
      })
    })
  })

  await page.goto('/entry/coil/2026-05-03/1')

  await page.getByRole('button', { name: '扫码带出' }).click()
  await expect(page.locator('input[placeholder="手工输入或扫码"]')).toHaveValue('TRACK-SCAN-1')
  await page.locator('input[placeholder="手工输入或扫码"]').fill('TRACK-SCAN-EDITED')
  await page.locator('input[type="number"]').nth(0).fill('1000')
  await page.locator('input[type="number"]').nth(1).fill('960')
  await page.getByRole('button', { name: '提交这卷' }).click()

  await expect.poll(() => submitPayload?.tracking_card_no).toBe('TRACK-SCAN-EDITED')
  expect(submitPayload.locked_fields_token).toBe('')
  expect(submitPayload.locked_fields_snapshot).toEqual({})
})

test('unified per-coil entry scans and submits editable submission fields', async ({ page }) => {
  let submitPayload = null

  await page.addInitScript(() => {
    sessionStorage.setItem('aluminum_bypass_token', 'scan-token')
    sessionStorage.setItem(
      'aluminum_bypass_user',
      JSON.stringify({
        id: 8,
        username: 'operator',
        name: '主操',
        role: 'machine_operator',
        workshop_id: 1,
        team_id: 10,
        data_scope_type: 'self_workshop',
        is_mobile_user: true,
        is_reviewer: false,
        is_manager: false
      })
    )
    window.dd = {
      biz: {
        util: {
          scan({ onSuccess }) {
            onSuccess({ text: 'QR-UNIFIED-1' })
          }
        }
      }
    }
  })

  await page.route('**/api/v1/mobile/current-shift', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-05-03',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '铸二车间',
        report_status: 'pending',
        can_submit: true
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
        groups: [
          {
            label: '产量数据',
            fields: [
              { name: 'tracking_card_no', label: '随行卡号', type: 'text', required: true },
              { name: 'alloy_grade', label: '合金', type: 'text', required: true },
              { name: 'input_spec', label: '来料规格', type: 'text', required: false },
              { name: 'input_weight', label: '投入重量', type: 'number', required: true },
              { name: 'output_weight', label: '产出重量', type: 'number', required: true }
            ]
          }
        ],
        readonly_fields: []
      })
    })
  })

  await page.route('**/api/v1/mobile/coil-list/2026-05-03/1', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })

  await page.route('**/api/v1/mobile/scan-lookup?**', async (route) => {
    expect(route.request().url()).toContain('qr=QR-UNIFIED-1')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source: 'coil_snapshot',
        header_fields: {
          tracking_card_no: 'TRACK-UNIFIED-1',
          alloy_grade: '6061',
          input_spec: '1.2×1200',
          current_process: '冷轧',
          next_process: '退火'
        },
        lock_keys: [],
        lock_token: null
      })
    })
  })

  await page.route('**/api/v1/mobile/coil-entry', async (route) => {
    submitPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 2,
        tracking_card_no: 'TRACK-UNIFIED-1',
        alloy_grade: '6061',
        input_spec: '1.2×1200',
        input_weight: 1000,
        output_weight: 960,
        scrap_weight: 40,
        operator_notes: '',
        extra_payload: {},
        business_date: '2026-05-03'
      })
    })
  })

  await page.goto('/entry/fill')

  await page.getByRole('button', { name: '扫码带出' }).click()
  await expect(page.locator('[data-testid="field-tracking_card_no"] input')).toHaveValue('TRACK-UNIFIED-1')
  await page.locator('[data-testid="field-tracking_card_no"] input').fill('TRACK-UNIFIED-EDITED')
  await page.locator('[data-testid="field-input_weight"] input').fill('1000')
  await page.locator('[data-testid="field-output_weight"] input').fill('960')
  await page.getByRole('button', { name: '录入本卷' }).click()

  await expect.poll(() => submitPayload?.tracking_card_no).toBe('TRACK-UNIFIED-EDITED')
  expect(submitPayload.locked_fields_token).toBe('')
  expect(submitPayload.locked_fields_snapshot).toEqual({})
})
