import { test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const OUT = process.env.VISUAL_OUT || 'test-results/manage'

for (const name of ['live', 'production', 'coils', 'alerts']) {
  test(`manage ${name}`, async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`/manage/${name}`)
    await page.waitForTimeout(3000)
    await page.screenshot({ path: `${OUT}/${name}-full.png`, fullPage: true })
  })
}

for (const name of ['workshop-dashboard', 'fill-details', 'energy', 'attendance', 'inventory', 'contracts', 'ai-assistant', 'master', 'admin/users', 'admin/settings', 'admin/agents', 'channels', 'rag', 'mapping-reconciliation', 'reports', 'factory/destinations']) {
  test(`manage more ${name}`, async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`/manage/${name}`)
    await page.waitForTimeout(2500)
    await page.screenshot({ path: `${OUT}/${name.replaceAll('/', '-')}.png` })
  })
}
