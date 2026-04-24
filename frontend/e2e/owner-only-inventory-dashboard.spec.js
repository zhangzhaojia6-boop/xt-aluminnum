import { expect, test } from '@playwright/test'

const inventoryUsername = process.env.PLAYWRIGHT_OWNER_USERNAME || 'CPK-A-INV'
const inventoryPassword = process.env.PLAYWRIGHT_OWNER_PASSWORD || '506371'
const adminUsername = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin'
const adminPassword =
  process.env.PLAYWRIGHT_ADMIN_PASSWORD ||
  process.env.PLAYWRIGHT_PASSWORD ||
  process.env.INIT_ADMIN_PASSWORD ||
  'Admin#Gate2026_Strong'

function parseMetric(text) {
  const normalized = String(text || '').replace(/,/g, '')
  const match = normalized.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : 0
}

function resolveBusinessDate(payload) {
  const value = payload?.business_date
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || '')) ? String(value) : new Date().toISOString().slice(0, 10)
}

async function setFactoryTargetDate(page, businessDate) {
  const dateInput = page.locator('.review-home-hero__controls .el-date-editor input').first()
  await expect(dateInput).toBeVisible()
  await dateInput.click()
  await dateInput.fill(businessDate)
  await dateInput.press('Enter')
  await expect(dateInput).toHaveValue(businessDate)
}

async function ensureFactoryDetailExpanded(page) {
  const toggle = page.locator('.review-factory-detail-toggle__btn').first()
  if (!(await toggle.count())) return
  const label = String(await toggle.innerText()).trim()
  if (label.includes('展开')) {
    await toggle.click()
  }
}

test('inventory owner can submit and factory dashboard reflects the new shipment metric', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(inventoryUsername)
  await page.getByTestId('login-password').fill(inventoryPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)

  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '成品库填报' })).toBeVisible()
  await expect(page.getByRole('button', { name: '下一步' })).toBeVisible()
  await expect(page.getByText('今日入库', { exact: true })).toBeVisible()
  await expect(page.getByText('今日发货', { exact: true })).toBeVisible()

  const submittedAt = Date.now()
  const inboundWeight = 20 + (submittedAt % 10)
  const shipmentWeight = 10 + (submittedAt % 7)
  const inventoryWeight = 30 + (submittedAt % 9)
  const consignmentWeight = 2

  await page.getByPlaceholder('请输入入库成品').fill(String(inboundWeight))
  await page.getByPlaceholder('请输入对外发货').fill(String(shipmentWeight))

  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('结存与备料', { exact: true })).toBeVisible()
  await page.getByPlaceholder('请输入寄存吨位').fill(String(consignmentWeight))
  await page.getByPlaceholder('请输入成品库存').fill(String(inventoryWeight))
  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('确认提交', { exact: true })).toBeVisible()
  const submitResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/entries/') &&
    response.url().endsWith('/submit') &&
    response.status() === 200
  )
  await page.locator('button').filter({ hasText: '正式提交' }).last().click()
  const submitPayload = await (await submitResponse).json()
  const submittedBusinessDate = resolveBusinessDate(submitPayload)

  const adminContext = await browser.newContext({ ignoreHTTPSErrors: true })
  const adminPage = await adminContext.newPage()
  try {
    await adminPage.goto('/login')
    await adminPage.getByTestId('login-username').fill(adminUsername)
    await adminPage.getByTestId('login-password').fill(adminPassword)
    await adminPage.getByTestId('login-submit').click()
    await expect(adminPage).toHaveURL(/\/review\/(overview|factory)/)
    await adminPage.goto('/review/factory')
    await setFactoryTargetDate(adminPage, submittedBusinessDate)
    await ensureFactoryDetailExpanded(adminPage)

    const shipmentCard = adminPage.locator('.stat-card').filter({ hasText: '今日发货' }).first()
    await expect(shipmentCard).toBeVisible()
    await expect.poll(
      async () => parseMetric(await shipmentCard.locator('.stat-value').innerText()),
      { timeout: 10000 }
    ).toBeGreaterThanOrEqual(shipmentWeight)
  } finally {
    await adminContext.close()
  }
})
