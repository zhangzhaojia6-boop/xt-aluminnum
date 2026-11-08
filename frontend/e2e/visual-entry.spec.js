import { test } from '@playwright/test'
import { setupStoredFillOnlySession } from './helpers/fill-only-session'
import { setupUnifiedPerCoilEntrySession } from './helpers/unified-entry-mocks'

const OUT = process.env.VISUAL_OUT || 'test-results/entry'
const SIZE = { width: 375, height: 812 }

async function shoot(page, name) {
  await page.waitForTimeout(2200)
  await page.screenshot({ path: `${OUT}/${name}.png` })
  await page.screenshot({ path: `${OUT}/${name}-full.png`, fullPage: true })
}

for (const [name, path] of [
  ['home', '/entry'],
  ['history', '/entry/history'],
  ['drafts', '/entry/drafts'],
  ['attendance', '/entry/attendance'],
  ['consumables', '/entry/consumables'],
  ['report', '/entry/report/2026-11-07/1'],
  ['coil', '/entry/coil/2026-11-07/1'],
  ['ocr', '/entry/ocr/2026-11-07/1']
]) {
  test(`entry ${name}`, async ({ page }) => {
    await setupStoredFillOnlySession(page)
    await page.setViewportSize(SIZE)
    await page.goto(path)
    await shoot(page, name)
  })
}

test('entry fill', async ({ page }) => {
  await setupUnifiedPerCoilEntrySession(page)
  await page.setViewportSize(SIZE)
  await page.goto('/entry/fill')
  await shoot(page, 'fill')
})
