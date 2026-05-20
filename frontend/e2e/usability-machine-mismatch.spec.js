import { expect, test } from '@playwright/test'

const PILOT_USER = {
  id: 8,
  username: 'operator',
  name: '主操',
  role: 'machine_operator',
  workshop_id: 1,
  team_id: 10,
  data_scope_type: 'self_workshop',
  is_mobile_user: true,
  is_reviewer: false,
  is_manager: false,
}

const BOUND_MACHINE_A = {
  machine_id: 21,
  machine_code: 'ZR2-1',
  machine_name: '1#机',
  workshop_id: 1,
  workshop_name: '铸二车间',
  qr_code: 'XT-ZR2-1',
}

async function seedSession(page, scanResult, scanQr, machineContext = BOUND_MACHINE_A) {
  await page.addInitScript(
    ({ user, machine, qr }) => {
      sessionStorage.setItem('aluminum_bypass_token', 'usability-token')
      sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(user))
      sessionStorage.setItem('aluminum_bypass_machine', JSON.stringify(machine))
      window.dd = {
        biz: { util: { scan({ onSuccess }) { onSuccess({ text: qr }) } } },
      }
    },
    { user: PILOT_USER, machine: machineContext, qr: scanQr },
  )

  await page.route('**/api/v1/mobile/bootstrap', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entry_mode: 'dingtalk_h5',
        dingtalk_enabled: true,
        user_has_dingtalk_binding: true,
        current_identity_source: 'dingtalk_oauth',
        workshop_id: machineContext.workshop_id,
        workshop_name: machineContext.workshop_name,
        machine_id: machineContext.machine_id,
        machine_code: machineContext.machine_code,
        machine_name: machineContext.machine_name,
        is_machine_bound: true,
        user_role: 'machine_operator',
      }),
    }),
  )

  await page.route('**/api/v1/mobile/current-shift', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        business_date: '2026-05-20',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: machineContext.workshop_id,
        workshop_name: machineContext.workshop_name,
        machine_id: machineContext.machine_id,
        machine_code: machineContext.machine_code,
        machine_name: machineContext.machine_name,
        report_status: 'pending',
        can_submit: true,
        is_machine_bound: true,
      }),
    }),
  )

  await page.route('**/api/v1/mobile/coil-list/2026-05-20/1', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  )

  if (scanResult === 'error_500') {
    await page.route('**/api/v1/mobile/scan-lookup?**', (route) =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '后端暂不可用' }),
      }),
    )
  } else {
    await page.route('**/api/v1/mobile/scan-lookup?**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(scanResult),
      }),
    )
  }
}

const baseHeaderFields = {
  tracking_card_no: 'TRACK-USE-1',
  alloy_grade: '6061',
  input_spec: '1.2×1200',
  current_workshop: '冷轧车间',
  current_process: '冷轧',
}

test('扫码命中机列与登录机列一致 — 静默放行，不出现机列警告', async ({ page }) => {
  await seedSession(
    page,
    {
      source: 'coil_snapshot',
      header_fields: baseHeaderFields,
      lock_keys: ['tracking_card_no', 'alloy_grade', 'input_spec'],
      lock_token: 'lock-1',
      machine_line_id: BOUND_MACHINE_A.machine_id,
      machine_line_code: BOUND_MACHINE_A.machine_code,
      machine_line_name: BOUND_MACHINE_A.machine_name,
      machine_binding_source: 'route_inferred',
    },
    'QR-USABILITY-MATCH',
  )

  await page.goto('/entry/coil/2026-05-20/1')
  await page.getByRole('button', { name: '扫码带出' }).click()

  await expect(page.locator('input[placeholder="手工输入或扫码"]')).toHaveValue('TRACK-USE-1')
  await expect(page.locator('.el-message--success')).toContainText('已带出卷头字段')
  await expect(page.locator('.el-message--warning')).toHaveCount(0)
})

test('扫码命中机列与登录机列错配 — 警告浮现，但 form 仍可继续', async ({ page }) => {
  await seedSession(
    page,
    {
      source: 'coil_snapshot',
      header_fields: baseHeaderFields,
      lock_keys: ['tracking_card_no', 'alloy_grade', 'input_spec'],
      lock_token: 'lock-mis',
      machine_line_id: 99,
      machine_line_code: 'LZ2050-7',
      machine_line_name: '2050冷轧7号',
      machine_binding_source: 'route_inferred',
    },
    'QR-USABILITY-MISMATCH',
  )

  await page.goto('/entry/coil/2026-05-20/1')
  await page.getByRole('button', { name: '扫码带出' }).click()

  await expect(page.locator('.el-message--warning')).toContainText('登录机列与 MES 推断不一致')
  await expect(page.locator('.el-message--warning')).toContainText('1#机')
  await expect(page.locator('.el-message--warning')).toContainText('2050冷轧7号')
  await expect(page.locator('input[placeholder="手工输入或扫码"]')).toHaveValue('TRACK-USE-1')
})

test('扫码命中多候选 unresolved — 不出警告，正常带出字段', async ({ page }) => {
  await seedSession(
    page,
    {
      source: 'coil_snapshot',
      header_fields: baseHeaderFields,
      lock_keys: ['tracking_card_no', 'alloy_grade', 'input_spec'],
      lock_token: 'lock-unresolved',
      machine_line_id: null,
      machine_line_code: null,
      machine_line_name: null,
      machine_binding_source: 'unresolved',
    },
    'QR-USABILITY-UNRES',
  )

  await page.goto('/entry/coil/2026-05-20/1')
  await page.getByRole('button', { name: '扫码带出' }).click()

  await expect(page.locator('input[placeholder="手工输入或扫码"]')).toHaveValue('TRACK-USE-1')
  await expect(page.locator('.el-message--warning')).toHaveCount(0)
})

test('扫码后端 500 — 不误触发机列错配警告', async ({ page }) => {
  await seedSession(page, 'error_500', 'QR-USABILITY-FAIL')

  await page.goto('/entry/coil/2026-05-20/1')
  await page.getByRole('button', { name: '扫码带出' }).click()

  await page.waitForTimeout(800)
  await expect(page.locator('.el-message--warning')).toHaveCount(0)
})
