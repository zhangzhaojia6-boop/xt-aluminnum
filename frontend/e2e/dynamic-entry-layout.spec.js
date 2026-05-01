import { expect, test } from '@playwright/test'
import { setupUnifiedPerCoilEntrySession } from './helpers/unified-entry-mocks'

test.use({ viewport: { width: 430, height: 932 }, isMobile: true, hasTouch: true })

test('machine entry form opens unified entry layout from the mobile home', async ({ page }) => {
  const trackingCard = `PW${Date.now()}`
  await setupUnifiedPerCoilEntrySession(page, {
    trackingCard,
    inputWeight: 1200,
    outputWeight: 1180
  })

  await page.goto('/entry')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/entry\/fill$/)
  await expect(page.getByTestId('unified-entry')).toBeVisible()
  await expect(page.getByRole('button', { name: '返回入口' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '录入本卷' })).toBeVisible()
  await expect(page.getByText('连续录入', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('随行卡号')).toBeVisible()
  await expect(page.getByLabel('合金')).toBeVisible()
  await expect(page.getByLabel(/投入重量/)).toBeVisible()
  await expect(page.getByLabel(/产出重量/)).toBeVisible()
  await expect(page.getByTestId('entry-mes-trace-card')).toHaveCount(0)
  await expect(page.getByText('外部系统线索')).toHaveCount(0)
  await expect(page.getByText('工艺路线', { exact: true })).toHaveCount(0)
  await expect(page.getByText('工单状态', { exact: true })).toHaveCount(0)

  await page.getByLabel('随行卡号').fill(trackingCard)
  await page.getByLabel('合金').fill('6063')
  await page.getByLabel(/投入重量/).fill('1200')
  await page.getByLabel(/产出重量/).fill('1180')
  await page.getByRole('button', { name: '录入本卷' }).click()

  await expect(page.getByText('第1卷 录入成功')).toBeVisible()
})
