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
  assert.match(src, /IndustrialProcessIcon/)
  assert.match(src, /MissingReportPanel/)
  assert.match(src, /useDashboardSnapshot/)
})

test('TodayPage h1 is the Stitch factory overview title with date context nearby', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /<h1>工厂总览<\/h1>/)
  assert.match(src, /统计周期：\{\{\s*businessDateLabel\s*\}\}/)
  assert.equal(/pageTitle/.test(src), false)
})

test('TodayPage exposes core page entrances including admin settings', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /\/manage\/live/)
  assert.match(src, /\/manage\/today\?section=daily-report/)
  assert.equal(/\/manage\/daily-report/.test(src), false)
  assert.match(src, /\/manage\/energy/)
  assert.match(src, /\/manage\/admin\/settings/)
  assert.match(src, /auth\.adminSurface/)
  assert.equal(/\/manage\/reports/.test(src), false)
})

test('TodayPage trims quick entrances on compact management clients', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /import\s+\{\s*isCompactClient\s*\}\s+from ['"]\.\.\/\.\.\/\.\.\/router\/guardRules\.js['"]/)
  assert.match(src, /const compactClient = ref\(isCompactClient\(\)\)/)
  assert.match(src, /if\s*\(\s*compactClient\.value\s*\)\s*return links/)
  assert.match(src, /window\.addEventListener\(['"]resize['"],\s*syncCompactClient/)
  assert.match(src, /window\.removeEventListener\(['"]resize['"],\s*syncCompactClient/)
})

test('TodayPage 数字卡 not bound to click handlers', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  // KpiBar usage in template should not have @click
  assert.equal(/<KpiBar[^>]*@click/.test(src), false)
})

test('TodayPage uses the Stitch industrial blue wall without expensive effects', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  const styleBlock = src.split('<style')[1] || ''
  assert.match(styleBlock, /#03111d/)
  assert.match(styleBlock, /#061d2e/)
  assert.match(styleBlock, /xt-today__command-wall/)
  assert.doesNotMatch(styleBlock, /animation:\s*[^;{}]*infinite/)
  assert.doesNotMatch(styleBlock, /backdrop-filter|filter:\s*blur/i)
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
  assert.match(src, /data-testid="today-command-wall"/)
  for (const label of ['生产流转总览', '算法主口径', '填报数据作对照', '车间产量概览', '过站下机参考', '在制料分布', '日累计']) {
    assert.match(src, new RegExp(label), `missing daily report label ${label}`)
  }
  assert.doesNotMatch(src, /primaryLabel:\s*'今日产出'/)
})

test('TodayPage binds daily report blocks to the daily overview payload', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /buildTodayStitchSurface/)
  assert.match(src, /snapshotData:\s*snapshot\.data\.value/)
  assert.match(src, /settlementCards\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.kpiStrip/)
  assert.match(src, /comparisonCards\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.comparisonRail/)
  assert.match(src, /workshopRows\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.workshopTable/)
  assert.match(src, /wipRows\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.wipDistribution/)
})

test('TodayPage shows total wip tons next to the position count', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /\{\{\s*wipRows\.length\s*\}\}\s*个位置\s*·\s*\{\{\s*wipTotalText\s*\}\}/)
  assert.match(src, /const wipTotalText\s*=\s*computed/)
  assert.match(src, /row\.totalWeight/)
})

test('TodayPage keeps factory command data basis in the Stitch wall', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /dailyOverview\s*=\s*computed\(\(\)\s*=>\s*snapshot\.data\.value\.daily_overview/)
  assert.match(src, /wipRows\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.wipDistribution/)
  assert.match(src, /productionFlowStages\s*=\s*computed/)
  assert.match(src, /shiftTiles\s*=\s*computed/)
})
