import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('TodayPage no longer imports OverviewCenter', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.equal(/OverviewCenter/.test(src), false)
})

test('TodayPage composes the 6 Phase B pieces', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /DateSwitcher/)
  assert.match(src, /KpiBar/)
  assert.match(src, /WorkshopBarChart/)
  assert.match(src, /KeyEventList/)
  assert.match(src, /CostLine/)
  assert.match(src, /SummaryHero/)
  assert.match(src, /useDashboardSnapshot/)
})

test('TodayPage h1 is the static tab title (date label lives in DateSwitcher)', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /<h1>今日<\/h1>/)
  assert.equal(/pageTitle/.test(src), false)
})

test('TodayPage 数字卡 not bound to click handlers', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  // KpiBar usage in template should not have @click
  assert.equal(/<KpiBar[^>]*@click/.test(src), false)
})

test('TodayPage uses --xt-* tokens, no hex in style block', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  const styleBlock = src.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(styleBlock), false)
})

test('TodayPage keeps KeyEventList always visible (无异常时常驻)', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  // KeyEventList 不再被 v-if 包裹——常驻显示，让"今日 0 异常"也能看见
  assert.equal(/<KeyEventList[\s\S]{0,80}v-if=/.test(src), false)
  assert.match(src, /<KeyEventList/)
})

test('TodayPage estimated_margin uses /10000 conversion to 万元', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /estimated_margin\)\s*\/\s*10000/)
})

test('TodayPage muted-state estimated_margin emits hint 估算未就绪', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /估算未就绪/)
})
