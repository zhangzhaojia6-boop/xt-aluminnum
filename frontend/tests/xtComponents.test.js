import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

// --- XtMetricCard ---

// --- XtDataTable ---

test('XtDataTable renders columns and rows from props', () => {
  const src = source('../src/components/xt/XtDataTable.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtDataTable' \}\)/)
  assert.match(src, /columns:/)
  assert.match(src, /data:/)
  assert.match(src, /v-for="col in columns"/)
  assert.match(src, /v-for="\(row, idx\) in data"/)
})

test('XtDataTable supports striped and compact modes', () => {
  const src = source('../src/components/xt/XtDataTable.vue')
  assert.match(src, /xt-data-table--striped/)
  assert.match(src, /xt-data-table--compact/)
  assert.match(src, /striped:/)
  assert.match(src, /compact:/)
})

test('XtDataTable shows empty state and supports cell slots', () => {
  const src = source('../src/components/xt/XtDataTable.vue')
  assert.match(src, /暂无数据/)
  assert.match(src, /cell-\$\{col\.key\}/)
  assert.match(src, /data-source/)
})

// --- XtSourceTag ---

// --- XtLineChart ---

test('XtLineChart registers echarts modules and accepts series/xLabels', () => {
  const src = source('../src/components/xt/XtLineChart.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtLineChart' \}\)/)
  assert.match(src, /series:/)
  assert.match(src, /xLabels:/)
  assert.match(src, /CanvasRenderer/)
  assert.match(src, /LineChart/)
  assert.match(src, /VChart/)
})

test('XtLineChart supports smooth and height props', () => {
  const src = source('../src/components/xt/XtLineChart.vue')
  assert.match(src, /smooth:/)
  assert.match(src, /height:/)
  assert.match(src, /240px/)
})

test('XtLineChart applies color palette to series', () => {
  const src = source('../src/components/xt/XtLineChart.vue')
  assert.match(src, /PALETTE/)
  assert.match(src, /#1f6feb/)
  assert.match(src, /s\.color \|\| PALETTE/)
})

// --- XtDashboardGrid ---

// --- XtSectionCard ---

// --- XtDrawer ---

// --- XtKpiRibbon ---
