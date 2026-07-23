import { expect, test } from '@playwright/test'

import { clearAuthStorage } from './helpers/mock-login.js'


async function setupOwnerDailySession(page) {
  const user = {
    id: 44,
    username: 'CPK-EC',
    name: '成品库内勤',
    role: 'storage_owner',
    workshop_id: 11,
    is_mobile_user: true,
    is_active: true,
  }
  let submittedPayload = null

  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(user),
  }))
  await page.route('**/api/v1/mobile/bootstrap', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      entry_mode: 'qr_role',
      current_identity_source: 'qr_role',
      current_scope_summary: { data_scope_type: 'self_workshop' },
      workshop_id: 11,
      workshop_name: '成品库',
      workshop_type: 'inventory',
      user_role: 'storage_owner',
    }),
  }))
  await page.route('**/api/v1/mobile/current-shift', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      business_date: '2026-07-19',
      shift_id: null,
      workshop_id: 11,
      workshop_name: '成品库',
      workshop_type: 'inventory',
      leader_name: '成品库内勤',
      report_status: 'unreported',
      can_submit: true,
      is_machine_bound: false,
      workshop_machines: [],
    }),
  }))
  await page.route('**/api/v1/mobile/entry-fields', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      mode: 'owner_daily',
      submit_target: 'owner_daily',
      role: 'storage_owner',
      role_label: '成品库',
      groups: [{
        label: '成品库',
        fields: [{
          name: 'finished_inbound_daily',
          label: '成品入库',
          type: 'number',
          unit: '吨',
          required: true,
        }, {
          name: 'park_inbound_daily',
          label: '园区入库日合',
          type: 'number',
          unit: '吨',
          required: false,
        }, {
          name: 'new_plant_inbound_daily',
          label: '新厂入库日合',
          type: 'number',
          unit: '吨',
          required: false,
        }],
      }],
      readonly_fields: [],
    }),
  }))
  await page.route('**/api/v1/mobile/owner-daily/**', (route) => {
    const businessDate = route.request().url().split('/').at(-1)
    const payload = businessDate === '2026-07-17'
      ? {
          id: 1701,
          business_date: businessDate,
          workshop_id: 11,
          workshop_name: '成品库',
          role: 'storage_owner',
          role_label: '成品库',
          data: { finished_inbound_daily: 85 },
          entry_status: 'submitted',
          updated_at: '2026-07-18T09:35:00+08:00',
        }
      : null
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    })
  })
  await page.route('**/api/v1/mobile/owner-daily', async (route) => {
    submittedPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1701,
        business_date: submittedPayload.business_date,
        workshop_id: 11,
        workshop_name: '成品库',
        role: 'storage_owner',
        role_label: '成品库',
        data: submittedPayload.data,
        entry_status: 'submitted',
        updated_at: '2026-07-19T12:00:00+08:00',
      }),
    })
  })

  await clearAuthStorage(page)
  await page.addInitScript(({ storedUser }) => {
    const token = 'playwright-owner-daily-token'
    localStorage.setItem('aluminum_bypass_token', token)
    localStorage.setItem('aluminum_bypass_user', JSON.stringify(storedUser))
    sessionStorage.setItem('aluminum_bypass_token', token)
    sessionStorage.setItem('aluminum_bypass_user', JSON.stringify(storedUser))
  }, { storedUser: user })

  return () => submittedPayload
}


test('owner daily can load and submit a recent historical business date on mobile', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const submittedPayload = await setupOwnerDailySession(page)

  await page.goto('/entry/fill')

  const dateSelect = page.getByLabel('业务日期')
  await expect(dateSelect).toBeVisible({ timeout: 15000 })
  await expect(dateSelect.locator('option')).toHaveCount(8)
  await dateSelect.selectOption('2026-07-17')
  await expect(page.getByLabel(/成品入库/)).toHaveValue('85')

  await page.getByLabel(/成品入库/).fill('86')
  await page.getByRole('button', { name: '提交 2026-07-17' }).click()

  await expect.poll(() => submittedPayload()?.business_date).toBe('2026-07-17')
  expect(submittedPayload()?.data.finished_inbound_daily).toBe(86)
  await expect(page.getByText('成品入库 86吨')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('owner-daily-backfill.png'), fullPage: true })
})


test('Hermes fact action link focuses every visible storage field without changing role access', async ({ page }, testInfo) => {
  const viewport = testInfo.project.name === 'mobile'
    ? { width: 390, height: 844 }
    : { width: 1280, height: 900 }
  await page.setViewportSize(viewport)
  await setupOwnerDailySession(page)

  await page.goto(
    '/entry/fill?business_date=2026-07-17'
    + '&field=finished_inbound_daily'
    + '&entry_fields=park_inbound_daily%2Cnew_plant_inbound_daily'
    + '&entry_field=park_inbound_daily'
    + '&owner_role=storage_owner'
    + '&trace_id=daily-fact-closure%3A2026-07-17'
  )

  await expect(page.getByLabel('业务日期')).toHaveValue('2026-07-17')
  await expect(page.getByTestId('field-park_inbound_daily')).toHaveClass(/ue-field--requested/)
  await expect(page.getByTestId('field-new_plant_inbound_daily')).toHaveClass(/ue-field--requested/)
  await expect(page.getByTestId('field-finished_inbound_daily')).not.toHaveClass(/ue-field--requested/)
  await expect(page.getByLabel(/园区入库日合/)).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath(`fact-action-fields-${testInfo.project.name}.png`),
    fullPage: true,
  })
})
