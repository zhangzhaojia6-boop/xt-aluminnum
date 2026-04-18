import { expect, test } from '@playwright/test'

const utilityUsername = process.env.PLAYWRIGHT_UTILITY_USERNAME || 'CPK-A-UTILITY'
const utilityPassword = process.env.PLAYWRIGHT_UTILITY_PASSWORD || '591767'
const adminUsername = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin'
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'Admin@123456'

function parseMetric(text) {
  const normalized = String(text || '').replace(/,/g, '')
  const match = normalized.match(/-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : 0
}

test('utility owner can submit and workshop dashboard reflects owner-only water usage', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(utilityUsername)
  await page.getByTestId('login-password').fill(utilityPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/mobile$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/mobile\/report-advanced\//)

  await page.getByRole('button', { name: '下一步' }).click()
  const inputs = page.locator('.mobile-field input')
  await expect(inputs).toHaveCount(10)

  const totalElectricity = 100 + (Date.now() % 20)
  const totalGas = 30 + (Date.now() % 10)
  const groundWater = 5 + (Date.now() % 3)
  const tapWater = 3 + (Date.now() % 2)
  await inputs.nth(0).fill(String(totalElectricity))
  await inputs.nth(7).fill(String(totalGas))
  await inputs.nth(8).fill(String(groundWater))
  await inputs.nth(9).fill(String(tapWater))

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
    await expect(adminPage).toHaveURL(/\/dashboard\/factory/)
    await adminPage.goto('/dashboard/workshop')
    await adminPage.locator('.header-actions .el-select .el-select__wrapper').click()
    await adminPage.locator('.el-select-dropdown__item').filter({ hasText: '成品库' }).last().click()

    const energyPanel = adminPage.locator('.panel').filter({ hasText: '能耗泳道' }).first()
    await expect(energyPanel).toBeVisible()
    await expect.poll(
      async () => await energyPanel.textContent(),
      { timeout: 10000 }
    ).toContain('owner_only')
    await expect.poll(
      async () => parseMetric(await energyPanel.textContent()),
      { timeout: 10000 }
    ).toBeGreaterThanOrEqual(groundWater + tapWater)
  } finally {
    await adminContext.close()
  }
})
