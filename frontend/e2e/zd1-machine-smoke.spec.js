import { expect, test } from '@playwright/test'
import { setupUnifiedPerCoilEntrySession } from './helpers/unified-entry-mocks'

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement
    return {
      windowWidth: window.innerWidth,
      documentWidth: root.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }
  })
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.windowWidth + 1)
  expect(overflow.bodyWidth).toBeLessThanOrEqual(overflow.windowWidth + 1)
}

test('machine account can submit a mobile entry', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const trackingCard = `PW${Date.now()}`
  await setupUnifiedPerCoilEntrySession(page, {
    trackingCard,
    inputWeight: 1200,
    outputWeight: 1180
  })

  await page.goto('/entry')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('mobile-current-shift')).toBeVisible()
  await expect(page.getByTestId('mobile-go-report')).toBeVisible()

  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/entry\/fill$/)
  await expect(page.getByTestId('unified-entry')).toBeVisible()
  await expect(page.getByTestId('entry-mes-trace-card')).toHaveCount(0)
  await expect(page.getByText('外部系统线索')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByLabel('随行卡号').fill(trackingCard)
  await page.getByLabel('合金').fill('6063')
  await page.getByLabel(/投入重量/).fill('1200')
  await page.getByLabel(/产出重量/).fill('1180')
  await expect(page.getByPlaceholder('请输入电耗')).toHaveCount(0)

  await expectNoHorizontalOverflow(page)
  const submitButton = page.getByRole('button', { name: '录入本卷' })
  await expect(submitButton).toBeEnabled()

  await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/coil-entry') &&
      response.request().method() === 'POST' &&
      response.status() === 200
    ),
    submitButton.click()
  ])
  await expect(page.getByText('第1卷 录入成功')).toBeVisible()
})
