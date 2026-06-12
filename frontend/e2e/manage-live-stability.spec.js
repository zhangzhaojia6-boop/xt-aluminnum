import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const enabled = process.env.RUN_LIVE_STABILITY === '1'
const seconds = Number(process.env.LIVE_STABILITY_SECONDS || 1800)
const sampleIntervalMs = Number(process.env.LIVE_STABILITY_SAMPLE_MS || 30000)
const safeSeconds = Number.isFinite(seconds) && seconds > 0 ? seconds : 1800
const safeSampleIntervalMs = Number.isFinite(sampleIntervalMs) && sampleIntervalMs > 0
  ? sampleIntervalMs
  : 30000

test.describe('manage live long-running stability', () => {
  test.skip(!enabled, 'set RUN_LIVE_STABILITY=1 to run the long-running /manage/live stability check')

  test('keeps the realtime dispatch wall readable without overflow', async ({ page }) => {
    test.setTimeout((safeSeconds * 1000) + 120000)

    await setupReviewSessionAndMocks(page)
    await page.setViewportSize({ width: 1366, height: 820 })
    await page.goto('/manage/live')

    const deadline = Date.now() + (safeSeconds * 1000)
    let samples = 0
    while (Date.now() < deadline) {
      await expect(page.getByTestId('manage-live')).toBeVisible()
      await expect(page.getByText('生产流转总览')).toBeVisible()
      await expect(page.getByTestId('stitch-bottom-status')).toContainText('能耗采集')

      const overflow = await page.evaluate(() => Math.max(
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
        document.body.scrollWidth - document.body.clientWidth
      ))
      expect(overflow).toBeLessThanOrEqual(1)

      samples += 1
      const remainingMs = deadline - Date.now()
      if (remainingMs <= 0) break
      await page.waitForTimeout(Math.min(safeSampleIntervalMs, remainingMs))
    }

    expect(samples).toBeGreaterThan(0)
  })
})
