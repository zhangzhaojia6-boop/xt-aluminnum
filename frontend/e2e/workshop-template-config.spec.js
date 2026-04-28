import { expect, test } from '@playwright/test'

const adminUsername = process.env.PLAYWRIGHT_ADMIN_USERNAME || process.env.PLAYWRIGHT_USERNAME || 'admin'
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD || process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'

test('admin can access workshop templates and machine user consumes updated template fields', async ({ page }) => {
  const fieldName = `qa_field_${Date.now()}`
  const fieldLabel = `测试字段${Date.now()}`

  await page.goto('/login')
  await page.getByTestId('login-username').fill(adminUsername)
  await page.getByTestId('login-password').fill(adminPassword)
  await page.getByTestId('login-submit').click()
  await page.waitForURL(/\/dashboard\/factory/)
  const token = await page.evaluate(() => localStorage.getItem('aluminum_bypass_token'))

  await page.goto('/master/workshop-template')
  await expect(page.getByTestId('template-editor-page')).toBeVisible()

  const authHeaders = { Authorization: `Bearer ${token}` }
  const detailResponse = await page.request.get('/api/v1/master/workshop-templates/ZD', {
    headers: authHeaders
  })
  expect(detailResponse.ok()).toBeTruthy()
  const original = await detailResponse.json()
  const updated = {
    display_name: original.display_name,
    tempo: original.tempo,
    supports_ocr: original.supports_ocr,
    entry_fields: original.entry_fields,
    extra_fields: [
      ...original.extra_fields,
      { name: fieldName, label: fieldLabel, type: 'text', unit: '', hint: '', compute: '', required: false, enabled: true }
    ],
    qc_fields: original.qc_fields,
    readonly_fields: original.readonly_fields
  }

  try {
    const updateResponse = await page.request.put('/api/v1/master/workshop-templates/ZD', {
      headers: authHeaders,
      data: updated
    })
    expect(updateResponse.ok()).toBeTruthy()

    const browser = page.context().browser()
    const machineContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 430, height: 932 }, isMobile: true, hasTouch: true })
    const machinePage = await machineContext.newPage()

    await machinePage.goto(`${process.env.PLAYWRIGHT_BASE_URL || 'https://127.0.0.1'}/login`)
    await machinePage.getByTestId('login-username').fill('ZD-1')
    await machinePage.getByTestId('login-password').fill('104833')
    await machinePage.getByTestId('login-submit').click()
    await machinePage.waitForURL(/\/mobile$/)
    await machinePage.getByTestId('mobile-go-report').click()
    await machinePage.waitForURL(/\/mobile\/report-advanced\//)
    await machinePage.locator('.mobile-inline-actions input').first().fill(`PW${Date.now()}`)
    await machinePage.getByRole('button', { name: '下一步' }).click()
    const coreInputs = machinePage.locator('.mobile-dynamic-form input')
    await coreInputs.nth(0).fill('6063')
    await coreInputs.nth(1).fill('6x1600')
    await coreInputs.nth(3).fill('1200')
    await machinePage.getByRole('button', { name: '下一步' }).click()

    await expect(machinePage.getByText(fieldLabel, { exact: true })).toBeVisible()
    await machineContext.close()
  } finally {
    await page.request.put('/api/v1/master/workshop-templates/ZD', {
      headers: authHeaders,
      data: {
        display_name: original.display_name,
        tempo: original.tempo,
        supports_ocr: original.supports_ocr,
        entry_fields: original.entry_fields,
        extra_fields: original.extra_fields,
        qc_fields: original.qc_fields,
        readonly_fields: original.readonly_fields
      }
    })
  }
})
