import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('TodayPage renders yesterday shift data inside the Stitch event rail', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /data-testid="today-event-rail"/)
  assert.match(src, /三班填报/)
  assert.match(src, /v-for="shift in shiftTiles"/)
  assert.match(src, /snapshot\.yesterdayShiftBreakdown\.value/)
})

test('TodayPage no longer mounts the legacy standalone shift panel', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.doesNotMatch(src, /import\s+YesterdayShiftPanel/)
  assert.doesNotMatch(src, /<YesterdayShiftPanel/)
})

test('useDashboardSnapshot exposes yesterdayShiftBreakdown', () => {
  const src = source('../src/composables/useDashboardSnapshot.js')
  assert.match(src, /yesterdayShiftBreakdown/)
  assert.match(src, /yesterday_shift_breakdown/)
})

test('YesterdayShiftPanel renders three shifts in A/B/C order', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  assert.match(src, /SHIFT_ORDER\s*=\s*\['A',\s*'B',\s*'C'\]/)
  assert.match(src, /大夜班/)
  assert.match(src, /长白班/)
  assert.match(src, /小夜班/)
})

test('YesterdayShiftPanel has dark HUD aesthetic (gradient bg, white headline)', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  const styleBlock = src.split('<style')[1] || ''
  assert.match(styleBlock, /linear-gradient/)
  assert.match(styleBlock, /#0d1320|#131b2e/)
})

test('YesterdayShiftPanel marks the leading shift', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  assert.match(src, /leaderIdx/)
  assert.match(src, /is-leader/)
})

test('YesterdayShiftPanel shows reported_workshops / expected_workshops ratio', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  assert.match(src, /reported_workshops/)
  assert.match(src, /expected_workshops/)
})

test('YesterdayShiftPanel uses throughput total for shift share', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  assert.match(src, /shiftShareTotal/)
  assert.match(src, /total_throughput/)
})
