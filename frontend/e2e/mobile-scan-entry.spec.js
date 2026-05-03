import { expect, test } from '@playwright/test'

test('mobile coil entry scans a coil qr and submits locked header fields', async ({ page }) => {
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
        lock_keys: ['tracking_card_no', 'alloy_grade', 'input_spec', 'current_workshop', 'current_process', 'next_workshop', 'next_process'],
        lock_token: 'signed-lock-token'
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
  await page.locator('input[type="number"]').nth(0).fill('1000')
  await page.locator('input[type="number"]').nth(1).fill('960')
  await page.getByRole('button', { name: '提交这卷' }).click()

  await expect.poll(() => submitPayload?.locked_fields_snapshot?.tracking_card_no).toBe('TRACK-SCAN-1')
  expect(submitPayload.locked_fields_token).toBe('signed-lock-token')
  expect(submitPayload.locked_fields_snapshot.alloy_grade).toBe('6061')
  expect(submitPayload.locked_fields_snapshot.input_spec).toBe('1.2×1200')
})
