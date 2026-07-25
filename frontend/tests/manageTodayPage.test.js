import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildTodayStitchSurface } from '../src/utils/stitchManageSurface.js'

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

test('TodayPage removes fixed source claims and relies on backend fact sources', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.doesNotMatch(src, /data-testid="second-pass-source-strip"/)
  assert.doesNotMatch(src, />MES 外部数据</)
  assert.doesNotMatch(src, />人工填报</)
  assert.doesNotMatch(src, />算法数据</)
  assert.match(src, /fact\.source/)
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

test('Today surface replaces overview guesses with confirmed or missing closure facts', () => {
  const surface = buildTodayStitchSurface({
    targetDate: '2026-07-07',
    snapshotData: {
      daily_overview: {
        plant_output: {
          daily_output: 999,
          finished_inbound_output: 888,
          yield_rate: 77,
        },
        fact_closure: {
          critical_fields: [
            {
              field: 'total_output_daily',
              value: 62,
              unit: '吨',
              status: 'confirmed',
              source: 'mes_packaging_output',
            },
            {
              field: 'finished_inbound_daily',
              value: null,
              unit: '吨',
              status: 'missing',
              source: null,
            },
            {
              field: 'daily_yield_rate',
              value: 93.4,
              unit: '%',
              status: 'confirmed',
              source: 'computed_same_basis',
            },
          ],
        },
      },
    },
  })

  const byKey = Object.fromEntries(surface.kpiStrip.map((item) => [item.key, item]))
  assert.equal(byKey['plant-output'].value, '62')
  assert.equal(byKey['plant-output'].sourceLabel, 'mes_packaging_output')
  assert.equal(byKey['finished-inbound'].value, '--')
  assert.equal(byKey['finished-inbound'].status, 'missing')
  assert.equal(byKey['finished-inbound'].sourceLabel, '暂无可信来源')
  assert.equal(byKey['yield-rate'].value, '93.4')
  assert.equal(byKey['yield-rate'].unit, '%')
})

test('TodayPage wires the persisted fact strip and trace drill-down to existing alerts', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /buildFactClosureSurface/)
  assert.match(src, /buildFactActionSummary/)
  assert.match(src, /dailyOverview\.value\.fact_closure/)
  assert.match(src, /dailyOverview\.value\.fact_missing/)
  assert.match(src, /useRouter/)
  assert.match(src, /openFactTrace/)
  assert.match(src, /function\s+openTrace\s*\(/)
  assert.match(src, /openFactTrace\(router,\s*traceId\)/)
  assert.match(src, /data-testid="today-fact-closure"/)
  assert.match(src, /data-testid="today-fact-actions"/)
})

test('TodayPage keeps the fact action arrow reachable on compact clients', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /const factActionRoute = computed/)
  assert.match(src, /compactClient\.value/)
  assert.match(src, /path:\s*['"]\/manage\/today['"]/)
  assert.match(src, /hash:\s*['"]#daily-report['"]/)
  assert.match(src, /path:\s*['"]\/manage\/alerts['"]/)
  assert.match(src, /domain:\s*['"]reporting['"]/)
  assert.match(src, /target_date:\s*snapshot\.targetDate\.value/)
  assert.match(src, /:to="factActionRoute"/)
})

test('TodayPage honors and preserves a target_date route query', () => {
  const src = source('../src/views/manage/today/TodayPage.vue')
  assert.match(src, /useRoute/)
  assert.match(src, /route\.query\.target_date/)
  assert.match(src, /snapshot\.targetDate\.value\s*=\s*initialTargetDate/)
  assert.match(src, /target_date:\s*next/)
})

test('mobile Today keeps the report date on one horizontal row', () => {
  const today = source('../src/views/manage/today/TodayPage.vue')
  const switcher = source('../src/components/manage/DateSwitcher.vue')
  assert.match(switcher, /\.xt-date-switcher__label\s*\{[\s\S]*?white-space:\s*nowrap/)
  assert.match(today, /@media \(max-width:\s*720px\)[\s\S]*?\.xt-today__top-actions\s*\{[\s\S]*?display:\s*grid/)
  assert.match(today, /\.xt-today__top-actions\s+:deep\(\.xt-date-switcher\)\s*\{[\s\S]*?width:\s*100%/)
})
