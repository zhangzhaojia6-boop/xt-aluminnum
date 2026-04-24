import { expect, test } from '@playwright/test'

const contractUsername = process.env.PLAYWRIGHT_CONTRACT_USERNAME || 'CPK-A-PLAN'
const contractPassword = process.env.PLAYWRIGHT_CONTRACT_PASSWORD || '101901'
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

test('contract owner can submit and factory dashboard reflects the new contract metric', async ({ browser, page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(contractUsername)
  await page.getByTestId('login-password').fill(contractPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)

  await expect(page.getByRole('heading', { name: '计划科填报' })).toBeVisible()
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByText('当日合同', { exact: true })).toBeVisible()
  await expect(page.getByText('月累计与余合同', { exact: true })).toBeVisible()
  const dailyContractWeight = 50 + (Date.now() % 10)
  const dailyInputWeight = 20 + (Date.now() % 5)
  await page.getByTestId('entry-core-form').getByPlaceholder('请输入当日接合同').fill(String(dailyContractWeight))

  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('投料与坯料', { exact: true })).toBeVisible()
  const supplementalPage = page.locator('.mobile-swipe-workspace__page[data-page-key="supplemental"]')
  await supplementalPage.getByPlaceholder('请输入当日投料').first().fill(String(dailyInputWeight))
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
    await expect(adminPage).toHaveURL(/\/review\/(overview|factory)/)
    await adminPage.goto('/review/factory')
    await setFactoryTargetDate(adminPage, submittedBusinessDate)
    await ensureFactoryDetailExpanded(adminPage)

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
