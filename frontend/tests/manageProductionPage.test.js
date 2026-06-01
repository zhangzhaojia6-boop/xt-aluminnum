import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

const SRC = source('../src/views/manage/production/ProductionPage.vue')

test('ProductionPage uses single-API useDashboardSnapshot composable', () => {
  assert.match(SRC, /useDashboardSnapshot/)
})

test('ProductionPage imports DateSwitcher and KpiBar (no duplication)', () => {
  assert.match(SRC, /DateSwitcher/)
  assert.match(SRC, /KpiBar/)
  assert.match(SRC, /FactorySourceStrip/)
})

test('ProductionPage renders workshop name as text (no dead deep-link to unimplemented route)', () => {
  assert.equal(/RouterLink/.test(SRC), false)
  assert.equal(/\/manage\/production\/workshop\//.test(SRC), false)
})

test('ProductionPage exposes the 5 KPI labels from current output contract', () => {
  for (const label of ['入库产量', '比昨日', '估算毛利', '合同缺口', '日吨能耗']) {
    assert.match(SRC, new RegExp(label), `missing KPI label ${label}`)
  }
})

test('ProductionPage labels target_value column suffix as 月均 (not 目标 / 达成率)', () => {
  assert.match(SRC, /月均/)
  assert.equal(/达成率/.test(SRC), false)
  assert.equal(/落后|超额/.test(SRC), false)
})

test('ProductionPage does not render weekly/monthly toggle buttons', () => {
  // 周/月 must not appear as standalone button text
  assert.equal(/<button[^>]*>\s*周\s*<\/button>/.test(SRC), false)
  assert.equal(/<button[^>]*>\s*月\s*<\/button>/.test(SRC), false)
  assert.equal(/切换周|切换月/.test(SRC), false)
})

test('ProductionPage converts estimated_margin to 万元 via division by 10000', () => {
  assert.match(SRC, /estimated_margin[\s\S]{0,40}\/\s*10000/)
})

test('ProductionPage shows 估算未就绪 hint when margin is not ready', () => {
  assert.match(SRC, /估算未就绪/)
})

test('ProductionPage sorts workshop ranking by total_output descending', () => {
  // b.total_output appears before a.total_output inside .sort callback => desc
  assert.match(SRC, /\.sort\([\s\S]*?b\.total_output[\s\S]*?a\.total_output/)
})

test('ProductionPage references target_value and renders em-dash for null', () => {
  assert.match(SRC, /target_value/)
  assert.match(SRC, /—/)
})

test('ProductionPage style block uses --xt-* tokens, no hex colors', () => {
  const styleBlock = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(styleBlock), false)
  assert.match(styleBlock, /var\(--xt-/)
})

test('ProductionPage KPI cards have no @click bindings (not navigable)', () => {
  assert.equal(/<KpiBar[^>]*@click/.test(SRC), false)
})

test('ProductionPage shows empty placeholder when production_lane is empty', () => {
  assert.match(SRC, /无车间数据/)
})

test('ProductionPage shows the same factory command source basis as today page', () => {
  assert.match(SRC, /<FactorySourceStrip[\s\S]*:overview="snapshot\.factoryCommandOverview\.value"/)
})
