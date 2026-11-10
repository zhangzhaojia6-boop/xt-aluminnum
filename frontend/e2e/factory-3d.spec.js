import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const WORKSHOP_OUTPUT = [
  { workshop_id: 2, workshop: '铸轧二', daily_output: 182.4, monthly_output: 1800, delta: 3 },
  { workshop_id: 4, workshop: '热轧', daily_output: null, monthly_output: 900, delta: null },
  { workshop_id: 10, workshop: '剪切车间', daily_output: 33.25, monthly_output: 300, delta: 1 }
]

async function openFactory(page) {
  await setupReviewSessionAndMocks(page)
  await page.route(/\/api\/v1\/dashboard\/daily-production/, async (route) => {
    await route.fulfill({ json: { workshop_output: WORKSHOP_OUTPUT, plant_output: {} } })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/manage/factory-3d')
  await expect(page.getByTestId('manage-factory-3d')).toBeVisible()
}

test('3D factory lays real workshops on the plant plan and opens the workshop board', async ({ page }) => {
  await openFactory(page)
  const stage = page.getByTestId('factory-stage')
  await expect(stage).toHaveAttribute('data-mode', /^(3d|2d)$/)

  const castTwo = stage.getByTestId('factory-label').filter({ hasText: '铸轧二' })
  await expect(castTwo).toContainText('182.4')
  await expect(stage.getByTestId('factory-label').filter({ hasText: '热轧' })).toContainText('—')
  await expect(page.locator('.xt-factory3d__offmap')).toContainText('剪切车间')
  await expect(page.locator('.xt-factory3d__offmap')).toContainText('33.3')

  const aside = page.getByTestId('manage-shell').locator('.xt-manage__sidebar')
  await expect(aside.getByRole('link', { name: '3D 工厂' })).toHaveAttribute('aria-current', 'page')

  if ((await stage.getAttribute('data-mode')) === '3d') {
    await expect(page.getByTestId('factory-canvas')).toHaveAttribute('data-draw-calls', /^\d+$/)
    const calls = Number(await page.getByTestId('factory-canvas').getAttribute('data-draw-calls'))
    expect(calls).toBeGreaterThan(0)
    expect(calls).toBeLessThanOrEqual(60)
  }

  await castTwo.click()
  await expect(page).toHaveURL(/\/manage\/workshop-dashboard\?workshop_id=2$/)
})

test('reduced motion shows the 2D plant plan instead of WebGL', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openFactory(page)

  await expect(page.getByTestId('factory-stage')).toHaveAttribute('data-mode', '2d')
  await expect(page.getByTestId('factory-plan')).toBeVisible()
  await expect(page.locator('.xt-factory3d__stage canvas')).toHaveCount(0)
  await expect(page.getByTestId('factory-plan').getByTestId('factory-label').filter({ hasText: '铸轧二' })).toContainText('182.4')
})

test('3D code is only downloaded on the 3D page', async ({ page }) => {
  const threeRequests = []
  page.on('request', (request) => {
    if (/vendor-three|plant-scene|line-scene/.test(request.url())) threeRequests.push(request.url())
  })
  await setupReviewSessionAndMocks(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/manage/today')
  await expect(page.getByTestId('manage-today')).toBeVisible()
  await page.waitForLoadState('networkidle')
  expect(threeRequests).toEqual([])
})

test('phones are sent to the 2D workshop board', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/manage/factory-3d')
  await expect(page).not.toHaveURL(/factory-3d/)
})

test('a failed daily request shows a data error badge instead of pretending there is no output', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.route(/\/api\/v1\/dashboard\/(daily-production|factory-director)/, (route) => route.fulfill({ status: 500, json: { detail: 'boom' } }))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/manage/factory-3d')
  await expect(page.getByTestId('factory-data-error')).toBeVisible()
})
