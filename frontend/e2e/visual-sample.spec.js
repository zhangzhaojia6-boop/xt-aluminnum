import { readFileSync } from 'node:fs'
import { test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const OUT = process.env.VISUAL_OUT || 'test-results/sample'
const SAMPLE = process.env.VISUAL_SAMPLE_JSON ? JSON.parse(readFileSync(process.env.VISUAL_SAMPLE_JSON, 'utf8')) : null
const SIZES = [['desktop', 1440, 900], ['mobile', 375, 812]]

for (const [label, width, height] of SIZES) {
  test(`sample login ${label}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/login')
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${OUT}/login-${label}.png` })
  })

  test(`sample today ${label}`, async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    if (SAMPLE) {
      await page.route('**/api/v1/dashboard/daily-production**', (route) => route.fulfill({ json: SAMPLE.daily }))
      await page.route('**/api/v1/dashboard/timeseries**', (route) => route.fulfill({ json: SAMPLE.ts }))
    }
    await page.setViewportSize({ width, height })
    await page.goto('/manage/today?target_date=2026-11-07')
    await page.waitForTimeout(3000)
    await page.screenshot({ path: `${OUT}/today-${label}.png` })
    await page.mouse.wheel(0, 4000)
    await page.waitForTimeout(2500)
    await page.screenshot({ path: `${OUT}/today-${label}-full.png`, fullPage: true })
  })
}
