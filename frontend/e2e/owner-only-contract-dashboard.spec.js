import { expect, test } from '@playwright/test'

const contractUsername = process.env.PLAYWRIGHT_CONTRACT_USERNAME || 'CPK-A-PLAN'
const contractPassword = process.env.PLAYWRIGHT_CONTRACT_PASSWORD || '101901'

async function loginAsContractOwner(page) {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(contractUsername)
  await page.getByTestId('login-password').fill(contractPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
}

async function expectFillOnlyBoundary(page) {
  await page.goto('/review/factory')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('review-shell')).toHaveCount(0)

  await page.goto('/admin')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
}

test('contract owner uses the entry contract surface without review or admin access', async ({ page }) => {
  await loginAsContractOwner(page)

  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)
  await expect(page.getByRole('heading', { name: '计划科填报' })).toBeVisible()
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByText('当日合同', { exact: true })).toBeVisible()
  await expect(page.getByText('月累计与余合同', { exact: true })).toBeVisible()
  await expect(page.getByTestId('review-shell')).toHaveCount(0)
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)

  await expectFillOnlyBoundary(page)
})
