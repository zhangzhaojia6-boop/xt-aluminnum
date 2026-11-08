import { test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const OUT = process.env.VISUAL_OUT || 'test-results/baseline'
const PAGES = ['/login', '/manage/today', '/manage/live', '/manage/production', '/manage/coils', '/manage/alerts']
const SIZES = [['desktop', 1440, 900], ['mobile', 375, 812]]

for (const path of PAGES) {
  for (const [label, width, height] of SIZES) {
    test(`baseline ${path} ${label}`, async ({ page }) => {
      if (path !== '/login') await setupReviewSessionAndMocks(page)
      await page.setViewportSize({ width, height })
      await page.goto(path)
      await page.waitForTimeout(2500)
      const name = path.replaceAll('/', '_').replace(/^_/, '')
      await page.screenshot({ path: `${OUT}/${name}-${label}.png` })
    })
  }
}
