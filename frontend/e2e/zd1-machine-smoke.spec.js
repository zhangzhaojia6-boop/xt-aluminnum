import { expect, test } from '@playwright/test'

test('machine account can submit a mobile entry', async ({ page }) => {
  const trackingCard = `PW${Date.now()}`

  await page.goto('/login?machine=XT-ZD-1')

  await expect(page).toHaveURL(/\/(mobile|entry)$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('mobile-current-shift')).toBeVisible()
  await expect(page.getByTestId('mobile-role-bucket')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()

  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/(mobile\/report-advanced|entry\/advanced)\//)
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-summary-strip')).toBeVisible()

  await page.locator('.mobile-inline-actions input').first().fill(trackingCard)
  await page.getByRole('button', { name: '下一步' }).click()

  const formInputs = page.locator('.mobile-dynamic-form input')
  await formInputs.nth(0).fill('6063')
  await formInputs.nth(1).fill('6x1600')
  await formInputs.nth(3).fill('1200')
  await page.getByRole('button', { name: '下一步' }).click()
  await expect(page.getByText('班末补充确认', { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('请输入电耗')).toHaveCount(0)

  const actionButtons = page.locator('.mobile-sticky-actions__buttons button')
  await expect(actionButtons.nth(2)).toBeEnabled()
  await actionButtons.nth(2).click()
  await expect(page.getByText('确认提交', { exact: true })).toBeVisible()
  const submitButton = page.getByRole('button', { name: '正式提交' }).last()
  await expect(submitButton).toBeEnabled()

  await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes('/work-orders/entries/') &&
      response.url().endsWith('/submit') &&
      response.request().method() === 'POST' &&
      response.status() === 200
    ),
    submitButton.dispatchEvent('click')
  ])
})
