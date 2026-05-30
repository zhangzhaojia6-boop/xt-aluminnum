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

test('TodayPage composes the active overview pieces', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /DateSwitcher/)
  assert.match(src, /KpiBar/)
  assert.match(src, /WorkshopBarChart/)
  assert.match(src, /CostLine/)
  assert.match(src, /SummaryHero/)
  assert.match(src, /useDashboardSnapshot/)
})

test('TodayPage h1 is the static yesterday overview title (date label lives in DateSwitcher)', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /<h1>昨日总览<\/h1>/)
  assert.equal(/pageTitle/.test(src), false)
})

test('TodayPage exposes core page entrances including admin settings', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /\/manage\/live/)
  assert.match(src, /\/manage\/today\?section=daily-report/)
  assert.equal(/\/manage\/daily-report/.test(src), false)
  assert.match(src, /\/energy\/center/)
  assert.match(src, /\/manage\/admin\/settings/)
  assert.match(src, /auth\.adminSurface/)
  assert.equal(/\/manage\/reports/.test(src), false)
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

test('TodayPage keeps exception as an entrance without proactive prompts', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.equal(/KeyEventList/.test(src), false)
  assert.match(src, /\/manage\/alerts/)
})

test('TodayPage estimated_margin uses /10000 conversion to 万元', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /estimated_margin\)\s*\/\s*10000/)
})

test('TodayPage muted-state estimated_margin emits hint 估算未就绪', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /估算未就绪/)
})

test('TodayPage owns the daily report settlement section', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /data-testid="daily-report-section"/)
  for (const label of ['全厂入库产量', '过站下机参考', '合同吨数', '算法能耗', '电工填报', '算法成品率', '内勤对照', '外部 MES 当前在制']) {
    assert.match(src, new RegExp(label), `missing daily report label ${label}`)
  }
})

test('TodayPage binds daily report blocks to the daily overview payload', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /dailyOverview/)
  assert.match(src, /buildDailySettlementCards/)
  assert.match(src, /buildDailyComparisonCards/)
  assert.match(src, /buildDailyWorkshopRows/)
  assert.match(src, /buildDailyWipRows/)
})
