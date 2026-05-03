import { expect, test } from '@playwright/test'

test('dingtalk runtime auto logs in and lands on mobile entry', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window.navigator, 'userAgent', {
      get: () => 'Mozilla/5.0 DingTalk',
      configurable: true
    })
    window.__DINGTALK_CORP_ID__ = 'corp_100'
    window.dd = {
      config() {},
      runtime: {
        permission: {
          requestAuthCode({ onSuccess }) {
            onSuccess({ code: 'AUTH_CODE_100' })
          }
        }
      }
    }
  })

  await page.route('**/api/v1/dingtalk/h5-login', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.code).toBe('AUTH_CODE_100')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'dingtalk-token',
        token_type: 'bearer',
        user: {
          id: 7,
          username: 'leader_100',
          name: '一车间班长',
          role: 'machine_operator',
          workshop_id: 1,
          team_id: 10,
          dingtalk_user_id: 'dt_100',
          dingtalk_union_id: 'union_100',
          data_scope_type: 'self_team',
          assigned_shift_ids: [1],
          is_mobile_user: true,
          is_reviewer: false,
          is_manager: false
        },
        machine_info: {
          machine_id: 21,
          machine_code: 'ZR2-1',
          machine_name: '1#机',
          workshop_id: 1,
          workshop_name: '铸二车间',
          qr_code: 'XT-ZR2-1'
        }
      })
    })
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
        current_scope_summary: { data_scope_type: 'self_team' },
        workshop_id: 1,
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
        business_date: '2026-05-03',
        shift_id: 1,
        shift_name: '白班',
        workshop_id: 1,
        workshop_name: '铸二车间',
        workshop_type: 'casting',
        machine_id: 21,
        machine_code: 'ZR2-1',
        machine_name: '1#机',
        report_status: 'pending',
        can_submit: true,
        is_machine_bound: true
      })
    })
  })

  await page.route('**/api/v1/templates/casting', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ supports_ocr: false })
    })
  })

  await page.goto('/login')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('mobile-current-shift')).toBeVisible()
  await expect(page.getByText('1#机').first()).toBeVisible()
})
