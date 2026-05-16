import { expect, test } from '@playwright/test'

test.describe('Mobile Offline Draft', () => {
  test('offline draft page is accessible', async ({ page }) => {
    await page.goto('/entry')
    await expect(page.locator('body')).toBeVisible()
  })

  test('IndexedDB draft storage is available', async ({ page }) => {
    await page.goto('/entry')
    const hasIdb = await page.evaluate(() => 'indexedDB' in window)
    expect(hasIdb).toBe(true)
  })
})
