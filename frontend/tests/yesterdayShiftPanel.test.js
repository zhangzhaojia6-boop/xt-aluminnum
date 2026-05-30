import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('TodayPage mounts YesterdayShiftPanel before SummaryHero', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /<YesterdayShiftPanel/)
  const idxPanel = src.indexOf('<YesterdayShiftPanel')
  const idxHero = src.indexOf('<SummaryHero')
  assert.ok(idxPanel > 0 && idxHero > 0 && idxPanel < idxHero, 'panel must appear before SummaryHero')
})

test('TodayPage imports YesterdayShiftPanel component', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /import\s+YesterdayShiftPanel/)
})

test('useDashboardSnapshot exposes yesterdayShiftBreakdown', () => {
  const src = source('../src/composables/useDashboardSnapshot.js')
  assert.match(src, /yesterdayShiftBreakdown/)
  assert.match(src, /yesterday_shift_breakdown/)
})

test('YesterdayShiftPanel renders three shifts in C/A/B order', () => {
  const src = source('../src/components/manage/YesterdayShiftPanel.vue')
  assert.match(src, /SHIFT_ORDER\s*=\s*\['C',\s*'A',\s*'B'\]/)
  assert.match(src, /大夜/)
  assert.match(src, /长白班/)
  assert.match(src, /小夜/)
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
