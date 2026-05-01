import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 430, height: 932 }, isMobile: true, hasTouch: true })

test('machine entry form shows migration-first layout with grouped secondary sections', async ({ page }) => {
  await page.goto('/login?machine=XT-ZD-1')

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/entry\/advanced\//)
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('mobile-swipe-workspace')).toBeVisible()
  await expect(page.getByTestId('swipe-page-indicator')).toContainText('1 /')
  await expect(page.getByRole('button', { name: '返回入口' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '下一步' })).toBeVisible()
  await expect(page.getByText('连续录入', { exact: true })).toHaveCount(0)
  await expect(page.getByText('批次号', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('随行卡', { exact: true })).toHaveCount(0)
  await expect(page.getByText('备注', { exact: true })).toBeVisible()
  await expect(page.getByTestId('entry-mes-trace-card')).toHaveCount(0)
  await expect(page.getByText('外部系统线索')).toHaveCount(0)
  await expect(page.getByText('本班交接', { exact: true })).toBeVisible()
  await expect(page.getByText('工艺路线', { exact: true })).toHaveCount(0)
  await expect(page.getByText('工单状态', { exact: true })).toHaveCount(0)

  await page.locator('.mobile-inline-actions input').first().fill(`PW${Date.now()}`)
  await page.getByRole('button', { name: '下一步' }).click()

  const coreInputs = page.locator('.mobile-dynamic-form input')
  await coreInputs.nth(0).fill('6063')
  await coreInputs.nth(1).fill('6x1600')
  await coreInputs.nth(3).fill('1200')
  await page.getByRole('button', { name: '下一步' }).click()

  await expect(page.getByTestId('swipe-page-indicator')).toContainText('3 /')
  await expect(page.getByText('格纸炉 (kg)', { exact: true })).toBeVisible()
})
