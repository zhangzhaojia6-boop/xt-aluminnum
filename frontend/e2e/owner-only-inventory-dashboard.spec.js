import { expect, test } from '@playwright/test'

const inventoryUsername = process.env.PLAYWRIGHT_OWNER_USERNAME || 'CPK-A-INV'
const inventoryPassword = process.env.PLAYWRIGHT_OWNER_PASSWORD || '506371'

async function loginAsInventoryOwner(page) {
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
  await expect(page.getByRole('heading', { name: '成品库填报' })).toBeVisible()
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toHaveCount(0)
  await expect(page.getByText('今日入库', { exact: true })).toBeVisible()
  await expect(page.getByText('今日发货', { exact: true })).toBeVisible()
  await expect(page.getByTestId('manage-shell')).toHaveCount(0)

  await expectFillOnlyBoundary(page)
})
