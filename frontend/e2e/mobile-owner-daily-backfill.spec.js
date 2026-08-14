import { expect, test } from '@playwright/test'

import { clearAuthStorage } from './helpers/mock-login.js'


async function setupOwnerDailySession(page, options = {}) {
  const user = {
    id: 44,
    username: 'CPK-EC',
    name: '成品库内勤',
    role: 'storage_owner',
    workshop_id: 11,
    is_mobile_user: true,
    is_active: true,
    ...(options.user || {}),
  }
  const workshopName = options.workshopName || '成品库'
  const workshopType = options.workshopType || 'inventory'
  const roleLabel = options.roleLabel || '成品库'
  const fields = options.fields || [{
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
  }]
  const existingDataByDate = options.existingDataByDate || {
    '2026-07-17': { finished_inbound_daily: 85 },
  }
  let submittedPayload = null
  let submitAttempts = 0

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
      workshop_name: workshopName,
      workshop_type: workshopType,
      user_role: user.role,
    }),
  }))
  await page.route('**/api/v1/mobile/current-shift', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      business_date: '2026-07-19',
      shift_id: null,
      workshop_id: 11,
      workshop_name: workshopName,
      workshop_type: workshopType,
      leader_name: user.name,
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
      role: user.role,
      role_label: roleLabel,
      groups: [{
        label: roleLabel,
        fields,
      }],
      readonly_fields: [],
    }),
  }))
  await page.route('**/api/v1/mobile/owner-daily/**', (route) => {
    const businessDate = route.request().url().split('/').at(-1)
    const existingData = existingDataByDate[businessDate]
    const payload = existingData
      ? {
          id: 1701,
          business_date: businessDate,
          workshop_id: 11,
          workshop_name: workshopName,
          role: user.role,
          role_label: roleLabel,
          data: existingData,
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
    submitAttempts += 1
    if (options.failFirstSubmit && submitAttempts === 1) {
      await route.abort('failed')
      return
    }
    submittedPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1701,
        business_date: submittedPayload.business_date,
        workshop_id: 11,
        workshop_name: workshopName,
        role: user.role,
        role_label: roleLabel,
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
  await page.goto('/entry')
  await page.goto('/entry/fill?business_date=2026-07-17')
  await expect(page.getByRole('dialog', { name: '发现本机暂存内容' })).toHaveCount(0)
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
  await expect(page.getByLabel(/成品入库/)).toHaveCount(0)
  await expect(page.getByLabel(/园区入库日合/)).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath(`fact-action-fields-${testInfo.project.name}.png`),
    fullPage: true,
  })
})


test('owner daily survives a network interruption and replays one queued submission', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const submittedPayload = await setupOwnerDailySession(page, {
    existingDataByDate: {},
    failFirstSubmit: true,
  })

  await page.goto('/entry/fill?business_date=2026-07-17&entry_fields=finished_inbound_daily')
  await page.getByLabel(/成品入库/).fill('88')
  await page.getByRole('button', { name: '提交 2026-07-17' }).click()

  await expect(page.getByText('1 条等待网络恢复')).toBeVisible()
  await expect(page.getByRole('button', { name: '等待网络' })).toBeDisabled()

  await page.evaluate(() => window.dispatchEvent(new Event('online')))

  await expect.poll(() => submittedPayload()?.data?.finished_inbound_daily).toBe(88)
  await expect(page.getByText('1 条等待网络恢复')).toHaveCount(0)
  await expect(page.getByText(/已自动暂存/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '提交 2026-07-17' })).toBeEnabled()
})


test('overhaul owner can add and submit machine stop details from the existing fill page', async ({ page }, testInfo) => {
  const viewport = testInfo.project.name === 'mobile'
    ? { width: 390, height: 844 }
    : { width: 1280, height: 900 }
  await page.setViewportSize(viewport)
  const submittedPayload = await setupOwnerDailySession(page, {
    user: {
      username: 'DX-NQ',
      name: '大修内勤',
      role: 'overhaul_owner',
    },
    workshopName: '大修车间',
    workshopType: 'maintenance',
    roleLabel: '大修磨辊子+能耗',
    existingDataByDate: {},
    fields: [{
      name: 'machine_stop_records',
      label: '机器停机明细',
      type: 'machine_stop_list',
      required: false,
    }],
  })

  await page.goto(
    '/entry/fill?business_date=2026-07-17'
    + '&entry_fields=machine_stop_records'
    + '&owner_role=overhaul_owner'
    + '&trace_id=trace-machine-fill-e2e'
  )

  await expect(page.getByTestId('field-machine_stop_records')).toHaveClass(/ue-field--requested/)
  await page.getByLabel('机台').fill('2号机')
  await page.getByLabel('班次').fill('白班')
  await page.getByLabel('停机分钟').fill('42')
  await page.getByLabel('停机原因').fill('换辊待维修确认')
  await page.getByRole('button', { name: '添加停机记录' }).click()
  await expect(page.getByLabel('机台')).toHaveCount(2)
  await page.getByRole('button', { name: '删除第 2 条停机记录' }).click()
  await expect(page.getByLabel('机台')).toHaveCount(1)
  await page.getByRole('button', { name: '提交 2026-07-17' }).click()

  await expect.poll(() => submittedPayload()?.business_date).toBe('2026-07-17')
  expect(submittedPayload()?.data.machine_stop_records).toEqual([{
    workshop_name: '大修车间',
    machine_name: '2号机',
    machine_code: '',
    shift_name: '白班',
    downtime_minutes: 42,
    downtime_reason: '换辊待维修确认',
  }])
  await expect(page.getByText('2号机停机42分钟（换辊待维修确认）')).toBeVisible()
  await expect(page.getByText('[object Object]')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath(`machine-stop-fill-${testInfo.project.name}.png`),
    fullPage: true,
  })
})
