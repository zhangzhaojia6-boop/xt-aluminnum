import { test, expect } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test('missing energy remains unavailable instead of displaying zero consumption', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/dashboard/timeseries**', route => route.fulfill({ json: [
    { date: '2026-09-12', output: 484700, energy: null },
    { date: '2026-09-13', output: 234450, energy: null },
  ] }))
  await page.goto('/manage/today?target_date=2026-09-13')
  await page.locator('[aria-label="历史趋势"]').scrollIntoViewIfNeeded()
  await expect(page.getByTestId('manage-cost-line')).toContainText('暂无能耗数据')
  await expect(page.getByTestId('manage-cost-line')).not.toContainText('当日 0')
})

test('history charts match the light workspace and selected date on desktop and phone', async ({ page }, testInfo) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/dashboard/timeseries**', route => route.fulfill({ json: [
    { date: '2026-09-12', output: 484700, energy: 1000 },
    { date: '2026-09-13', output: 234450, energy: null },
  ] }))
  await page.route('**/api/v1/dashboard/daily-production**', route => route.fulfill({ json: {
    plant_output: { daily_output: 234.45 },
    workshop_output: Array.from({ length: 9 }, (_, index) => ({
      workshop_id: index, workshop: `生产车间 ${index + 1}`,
      daily_output: index === 8 ? null : 340 - index * 30, monthly_output: 2000,
    })),
  } }))
  await page.goto('/manage/today?target_date=2026-09-13')
  const charts = page.locator('[aria-label="历史趋势"]')
  await charts.scrollIntoViewIfNeeded()
  await expect(page.getByTestId('manage-cost-line')).toContainText('2026-09-13 估算成本')
  await expect(page.getByTestId('manage-workshop-bar')).toContainText('2026-09-13')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 })
    await expect(charts.locator('canvas').first()).toBeVisible()
    const backgrounds = await charts.locator('[data-testid]').evaluateAll(elements => elements.map(el => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = getComputedStyle(el).backgroundColor
      ctx.fillRect(0, 0, 1, 1)
      return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3)
    }))
    expect(backgrounds).toHaveLength(3)
    for (const rgb of backgrounds) expect(Math.min(...rgb)).toBeGreaterThan(220)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    // Canvas animation is independent of Playwright's CSS animation handling.
    await page.waitForTimeout(1200)
    await charts.screenshot({ path: testInfo.outputPath(`charts-${width}.png`) })
  }
})

test('KPI mini charts do not draw missing readings as a low point', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/dashboard/timeseries**', route => route.fulfill({ json: [
    { date: '2026-09-12', output: 100000, energy: 1000 },
    { date: '2026-09-13', output: null, energy: null },
  ] }))
  await page.goto('/manage/today?target_date=2026-09-13')
  await page.locator('[aria-label="历史趋势"]').scrollIntoViewIfNeeded()
  await expect(page.getByTestId('manage-output-trend')).toContainText('已知日均 100 吨')
  await expect(page.getByTestId('manage-kpi-bar').locator('svg.xt-spark')).toHaveCount(0)
})

test('production trend excludes missing readings and still displays confirmed zero readings', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  let readings = [
    { date: '2026-09-12', output: 100000, energy: 1000 },
    { date: '2026-09-13', output: null, energy: null },
  ]
  await page.route('**/api/v1/dashboard/timeseries**', route => route.fulfill({ json: readings }))
  await page.goto('/manage/today?target_date=2026-09-13')
  await page.locator('[aria-label="历史趋势"]').scrollIntoViewIfNeeded()
  const trend = page.getByTestId('manage-output-trend')
  await expect(trend).toContainText('日均 100 吨')
  readings = [{ date: '2026-09-13', output: 0, energy: 0 }]
  await page.reload()
  await page.locator('[aria-label="历史趋势"]').scrollIntoViewIfNeeded()
  await expect(trend).toContainText('日均 0 吨')
  await expect(trend.locator('canvas')).toBeVisible()
})

test('a missing last day stays missing when earlier energy readings are available', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/dashboard/timeseries**', route => route.fulfill({ json: [
    { date: '2026-09-12', output: 100000, energy: 1000 },
    { date: '2026-09-13', output: 234450, energy: null },
  ] }))
  await page.goto('/manage/today?target_date=2026-09-13')
  await page.locator('[aria-label="历史趋势"]').scrollIntoViewIfNeeded()
  await expect(page.getByTestId('manage-cost-line')).toContainText(/—.*均 10 kWh\/吨/)
})
