import { expect, test } from '@playwright/test'

const inventoryUsername = process.env.PLAYWRIGHT_OWNER_USERNAME || 'CPK-A-INV'
const inventoryPassword = process.env.PLAYWRIGHT_OWNER_PASSWORD || '506371'
const adminUsername = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin'
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'Admin@123456'

function parseMetric(text) {
  const normalized = String(text || '').replace(/,/g, '')
  const match = normalized.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : 0
}

test('inventory owner can submit and factory dashboard reflects the new shipment metric', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(inventoryUsername)
  await page.getByTestId('login-password').fill(inventoryPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/mobile$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/mobile\/report-advanced\//)

  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toHaveCount(0)

  const submittedAt = Date.now()
  const inboundWeight = 20 + (submittedAt % 10)
  const shipmentWeight = 10 + (submittedAt % 7)
  const inventoryWeight = 30 + (submittedAt % 9)
  const consignmentWeight = 2

  const inputs = page.locator('.mobile-field input')
  await expect(inputs).toHaveCount(13)
  await inputs.nth(0).fill(String(inboundWeight))
  await inputs.nth(6).fill(String(shipmentWeight))
  await inputs.nth(10).fill(String(consignmentWeight))
  await inputs.nth(11).fill(String(inventoryWeight))

  await page.getByRole('button', { name: '下一步' }).click()
  const submitResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/entries/') &&
    response.url().endsWith('/submit') &&
    response.status() === 200
  )
  await page.locator('button').filter({ hasText: '正式提交' }).last().click()
  await submitResponse

  const adminContext = await browser.newContext({ ignoreHTTPSErrors: true })
  const adminPage = await adminContext.newPage()
  try {
    await adminPage.goto('/login')
    await adminPage.getByTestId('login-username').fill(adminUsername)
    await adminPage.getByTestId('login-password').fill(adminPassword)
    await adminPage.getByTestId('login-submit').click()
    await expect(adminPage).toHaveURL(/\/dashboard\/factory/)

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
