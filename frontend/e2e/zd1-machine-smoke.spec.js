import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_MACHINE_USERNAME || 'ZD-1'
const password = process.env.PLAYWRIGHT_MACHINE_PASSWORD || '104833'

test('machine account can save a draft and submit a mobile entry', async ({ page }) => {
  const trackingCard = `PW${Date.now()}`

  await page.goto('/login')

  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/mobile$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('mobile-current-shift')).toBeVisible()
  await expect(page.getByTestId('mobile-role-bucket')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()

  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/mobile\/report-advanced\//)
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-summary-strip')).toBeVisible()

  await page.locator('.mobile-inline-actions input').first().fill(trackingCard)
  await page.getByRole('button', { name: '下一步' }).click()

  const formInputs = page.locator('.mobile-dynamic-form input')
  await formInputs.nth(0).fill('6063')
  await formInputs.nth(1).fill('6x1600')
  await formInputs.nth(3).fill('1200')

  const actionButtons = page.locator('.mobile-sticky-actions__buttons button')

  const draftResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/') &&
    response.url().includes('/entries') &&
    response.request().method() === 'POST' &&
    response.status() === 200
  )
  await expect(actionButtons.nth(1)).toBeEnabled()
  await actionButtons.nth(1).click()
  await draftResponse

  await expect(actionButtons.nth(2)).toBeEnabled()
  await actionButtons.nth(2).click()
  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByTestId('entry-secondary-sections')).toBeVisible()

  const submitResponse = page.waitForResponse((response) =>
    response.url().includes('/work-orders/entries/') &&
    response.url().endsWith('/submit') &&
    response.request().method() === 'POST' &&
    response.status() === 200
  )
  await page.locator('.mobile-sticky-actions__buttons button').filter({ hasText: '正式提交' }).last().click()
  await submitResponse
})
