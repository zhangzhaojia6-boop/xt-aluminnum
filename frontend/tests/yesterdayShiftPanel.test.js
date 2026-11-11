import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('TodayPage renders yesterday shift data inside the Stitch event rail', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /data-testid="today-event-rail"/)
  assert.doesNotMatch(src, /三班填报/)
  assert.doesNotMatch(src, /shiftTiles/)
})

test('useDashboardSnapshot exposes yesterdayShiftBreakdown', () => {
  const src = source('../src/composables/useDashboardSnapshot.js')
  assert.match(src, /yesterdayShiftBreakdown/)
  assert.match(src, /yesterday_shift_breakdown/)
})

