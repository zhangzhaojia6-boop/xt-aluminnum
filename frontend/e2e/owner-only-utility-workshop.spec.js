import { expect, test } from '@playwright/test'

const utilityUsername = process.env.PLAYWRIGHT_UTILITY_USERNAME || 'CPK-A-UTILITY'
const utilityPassword = process.env.PLAYWRIGHT_UTILITY_PASSWORD || '591767'
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

async function setWorkshopTargetDate(page, businessDate) {
  const dateInput = page.locator('.review-workshop__controls .el-date-editor input').first()
  await expect(dateInput).toBeVisible()
  await dateInput.click()
  await dateInput.fill(businessDate)
  await dateInput.press('Enter')
  await expect(dateInput).toHaveValue(businessDate)
}

async function fillMobileField(container, label, value) {
  await container
    .locator('.mobile-field', { hasText: label })
    .first()
    .getByRole('textbox')
    .fill(String(value))
}

test('utility owner can submit and workshop dashboard reflects owner-only water usage', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(utilityUsername)
  await page.getByTestId('login-password').fill(utilityPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)

  await expect(page.getByRole('heading', { name: '填水电气' })).toBeVisible()
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByText('用电', { exact: true })).toBeVisible()
  await expect(page.getByText('天然气', { exact: true })).toBeVisible()
  const totalElectricity = 100 + (Date.now() % 20)
  const totalGas = 30 + (Date.now() % 10)
  const groundWater = 5 + (Date.now() % 3)
  const tapWater = 3 + (Date.now() % 2)
  await fillMobileField(page.getByTestId('entry-core-form'), '全厂用电', totalElectricity)
  await fillMobileField(page.getByTestId('entry-core-form'), '天然气总量', totalGas)

  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('用水', { exact: true })).toBeVisible()
  const supplementalPage = page.locator('.mobile-swipe-workspace__page[data-page-key="supplemental"]')
  await fillMobileField(supplementalPage, '地下水', groundWater)
  await fillMobileField(supplementalPage, '自来水', tapWater)
  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('确认提交', { exact: true })).toBeVisible()
  const submitResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/entries/') &&
    response.url().endsWith('/submit') &&
    response.status() === 200
  )
  await page.locator('.mobile-sticky-actions__buttons button').filter({ hasText: '正式提交' }).last().click()
  const submitPayload = await (await submitResponse).json()
  const submittedBusinessDate = resolveBusinessDate(submitPayload)

  const adminContext = await browser.newContext({ ignoreHTTPSErrors: true })
  const adminPage = await adminContext.newPage()
  try {
    await adminPage.goto('/login')
    await adminPage.getByTestId('login-username').fill(adminUsername)
    await adminPage.getByTestId('login-password').fill(adminPassword)
    await adminPage.getByTestId('login-submit').click()
    await expect(adminPage).toHaveURL(/\/manage\/(overview|factory)/)
    await adminPage.goto('/manage/workshop')
    await expect(adminPage.getByTestId('manage-shell')).toBeVisible()
    await expect(adminPage.getByTestId('workshop-dashboard')).toBeVisible()
    await setWorkshopTargetDate(adminPage, submittedBusinessDate)
    await adminPage.locator('.review-workshop__controls .el-select .el-select__wrapper').click()
    await adminPage.locator('.el-select-dropdown__item').filter({ hasText: '成品库' }).last().click()
    const energySection = adminPage.locator('.el-collapse-item').filter({ hasText: '能耗泳道' }).first()
    const ownerEnergyRow = energySection.locator('.el-table__body tr').first()
    await expect(ownerEnergyRow).toBeVisible({ timeout: 10000 })
    await expect.poll(
      async () => parseMetric(await ownerEnergyRow.locator('td').nth(4).innerText()),
      { timeout: 10000 }
    ).toBeGreaterThanOrEqual(groundWater + tapWater)
  } finally {
    await adminContext.close()
  }
})
