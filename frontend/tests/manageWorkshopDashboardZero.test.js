import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue', import.meta.url), 'utf8')

test('workshop board does not show a live zero as a real tonnage', () => {
  assert.match(src, /reportedLiveTotal = \(value\) => \(Number\(value\) \? value : null\)/)
  assert.match(src, /reportedLiveTotal\(liveWorkshopTotal\.value\.input\)/)
  assert.match(src, /reportedLiveTotal\(liveWorkshopTotal\.value\.output\)/)
  assert.doesNotMatch(src, /formatNumber\(liveWorkshopTotal\.value\.input \?\?/)
})
