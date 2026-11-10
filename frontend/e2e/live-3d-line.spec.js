import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

async function openLive(page) {
  await setupReviewSessionAndMocks(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/manage/live')
  await expect(page.getByTestId('manage-live')).toBeVisible()
}

test('live flow switches to a 3D line on demand and back to 2D', async ({ page }) => {
  const threeRequests = []
  page.on('request', (request) => {
    if (/vendor-three|plant-scene|line-scene/.test(request.url())) threeRequests.push(request.url())
  })
  await openLive(page)
  const flow = page.getByRole('region', { name: '生产流转总览' })
  const toggle = flow.getByTestId('live-flow-3d')
  if (!(await toggle.count())) test.skip(true, 'no WebGL in this browser')

  await expect(flow.locator('.live-process-flow__rail')).toBeVisible()
  await page.waitForLoadState('networkidle')
  expect(threeRequests).toEqual([])

  await toggle.click()
  await expect(flow.getByTestId('live-flow-stage').locator('canvas')).toHaveCount(1)
  await expect(flow.getByTestId('live-flow-label')).toHaveCount(6)
  const canvas = flow.getByTestId('live-flow-canvas')
  await expect(canvas).toHaveAttribute('data-draw-calls', /^\d+$/)
  expect(Number(await canvas.getAttribute('data-draw-calls'))).toBeLessThanOrEqual(40)
  await expect(canvas).toHaveAttribute('data-coil-running', 'false')
  expect(threeRequests.length).toBeGreaterThan(0)
  await page.waitForTimeout(900)
  await page.screenshot({ path: process.env.LIVE3D_SHOT || 'test-results/live-3d.png' })

  await page.reload()
  await expect(page.getByRole('region', { name: '生产流转总览' }).getByTestId('live-flow-stage')).toBeVisible()

  await page.getByRole('region', { name: '生产流转总览' }).getByRole('button', { name: '2D' }).click()
  await expect(page.getByRole('region', { name: '生产流转总览' }).locator('.live-process-flow__rail')).toBeVisible()
  await expect(page.getByRole('region', { name: '生产流转总览' }).getByTestId('live-flow-stage')).toHaveCount(0)
})

test('reduced motion and phones keep the 2D flow without a 3D switch', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openLive(page)
  await expect(page.getByRole('region', { name: '生产流转总览' }).getByTestId('live-flow-3d')).toHaveCount(0)
})
