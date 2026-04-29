import { expect, test } from '@playwright/test'

const contractUsername = process.env.PLAYWRIGHT_CONTRACT_USERNAME || 'CPK-A-PLAN'
const contractPassword = process.env.PLAYWRIGHT_CONTRACT_PASSWORD || '101901'
const adminUsername = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin'
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'Admin@123456'

function parseMetric(text) {
  const normalized = String(text || '').replace(/,/g, '')
  const match = normalized.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : 0
}

test('contract owner can submit and factory dashboard reflects the new contract metric', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(contractUsername)
  await page.getByTestId('login-password').fill(contractPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/mobile$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/mobile\/report-advanced\//)
  const businessDate = new URL(page.url()).pathname.split('/').at(-2)

  await page.getByRole('button', { name: '下一步' }).click()
  const inputs = page.locator('.mobile-field input')
  await expect(inputs).toHaveCount(10)

  const dailyContractWeight = 50 + (Date.now() % 10)
  const dailyInputWeight = 20 + (Date.now() % 5)
  await inputs.nth(0).fill(String(dailyContractWeight))
  await inputs.nth(8).fill(String(dailyInputWeight))

  await page.getByRole('button', { name: '下一步' }).click()
  const submitResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/entries/') &&
    response.url().endsWith('/submit') &&
    response.status() === 200
  )
  await page.locator('.mobile-sticky-actions__buttons button').filter({ hasText: '正式提交' }).last().click()
  await submitResponse

  const adminContext = await browser.newContext({ ignoreHTTPSErrors: true })
  const adminPage = await adminContext.newPage()
  try {
    await adminPage.goto('/login')
    await adminPage.getByTestId('login-username').fill(adminUsername)
    await adminPage.getByTestId('login-password').fill(adminPassword)
    await adminPage.getByTestId('login-submit').click()
    await expect(adminPage).toHaveURL(/\/dashboard\/factory/, { timeout: 15000 })
    await adminPage.goto(`/dashboard/factory?target_date=${businessDate}`)

    const contractCard = adminPage.locator('.stat-card').filter({ hasText: '合同量' }).first()
    await expect(contractCard).toBeVisible()
    await expect.poll(
      async () => parseMetric(await contractCard.locator('.stat-value').innerText()),
      { timeout: 10000 }
    ).toBeGreaterThanOrEqual(dailyContractWeight)
  } finally {
    await adminContext.close()
  }
})
