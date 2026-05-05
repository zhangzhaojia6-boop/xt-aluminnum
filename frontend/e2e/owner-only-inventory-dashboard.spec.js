import { expect, test } from '@playwright/test'
import { firstEnv, skipWithoutCredentials } from './helpers/credentials'

const inventoryUsername = firstEnv('PLAYWRIGHT_INVENTORY_USERNAME')
const inventoryPassword = firstEnv('PLAYWRIGHT_INVENTORY_PASSWORD')

async function loginAsInventoryOwner(page) {
  skipWithoutCredentials([
    ['PLAYWRIGHT_INVENTORY_USERNAME', inventoryUsername],
    ['PLAYWRIGHT_INVENTORY_PASSWORD', inventoryPassword]
  ])

  await page.goto('/login')
  await page.getByTestId('login-username').fill(inventoryUsername)
  await page.getByTestId('login-password').fill(inventoryPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
}

async function expectFillOnlyBoundary(page) {
  await page.goto('/manage/factory')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)

  await page.goto('/manage/admin')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)
}

test('inventory owner uses the entry inventory surface without review or admin access', async ({ page }) => {
  await loginAsInventoryOwner(page)

  await page.getByTestId('mobile-go-report').click()
  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)
  await expect(page.getByRole('heading', { name: '填出入库' })).toBeVisible()
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toHaveCount(0)
  await expect(page.getByText('今日入库', { exact: true })).toBeVisible()
  await expect(page.getByText('今日发货', { exact: true })).toBeVisible()
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)

  await expectFillOnlyBoundary(page)
})
