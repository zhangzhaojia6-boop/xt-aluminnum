import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

// --- XtMetricCard ---

test('XtMetricCard declares required props and tone variants', () => {
  const src = source('../src/components/xt/XtMetricCard.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtMetricCard' \}\)/)
  assert.match(src, /label:/)
  assert.match(src, /value:/)
  assert.match(src, /unit:/)
  assert.match(src, /change:/)
  assert.match(src, /tone:/)
  assert.match(src, /neutral.*primary.*success.*warning.*danger/)
})

test('XtMetricCard formats large values with 万 suffix', () => {
  const src = source('../src/components/xt/XtMetricCard.vue')
  assert.match(src, /10000/)
  assert.match(src, /万/)
})

test('XtMetricCard tolerates missing metric values and changes', () => {
  const src = source('../src/components/xt/XtMetricCard.vue')
  assert.match(src, /Number\.isFinite\(props\.value\)/)
  assert.match(src, /return '—'/)
  assert.match(src, /hasChange/)
  assert.match(src, /Number\.isFinite\(props\.change\)/)
})

test('XtMetricCard shows change direction classes', () => {
  const src = source('../src/components/xt/XtMetricCard.vue')
  assert.match(src, /xt-metric-card__change--up/)
  assert.match(src, /xt-metric-card__change--down/)
})

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

test('XtSourceTag displays source and optional refreshedAt', () => {
  const src = source('../src/components/xt/XtSourceTag.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtSourceTag' \}\)/)
  assert.match(src, /source:/)
  assert.match(src, /refreshedAt:/)
  assert.match(src, /data-source/)
})

test('XtSourceTag renders icon and text elements', () => {
  const src = source('../src/components/xt/XtSourceTag.vue')
  assert.match(src, /xt-source-tag__icon/)
  assert.match(src, /xt-source-tag__text/)
  assert.match(src, /xt-source-tag__time/)
})

test('XtSourceTag uses inline-flex layout with gap', () => {
  const src = source('../src/components/xt/XtSourceTag.vue')
  assert.match(src, /display: inline-flex/)
  assert.match(src, /gap:/)
})

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

test('XtDashboardGrid uses CSS grid with configurable columns', () => {
  const src = source('../src/components/xt/XtDashboardGrid.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtDashboardGrid' \}\)/)
  assert.match(src, /columns:/)
  assert.match(src, /grid-template-columns/)
  assert.match(src, /--grid-columns/)
})

test('XtDashboardGrid supports gap variants', () => {
  const src = source('../src/components/xt/XtDashboardGrid.vue')
  assert.match(src, /tight.*normal.*wide/)
  assert.match(src, /--grid-gap/)
})

test('XtDashboardGrid has responsive breakpoints', () => {
  const src = source('../src/components/xt/XtDashboardGrid.vue')
  assert.match(src, /1200px/)
  assert.match(src, /768px/)
})

// --- XtSectionCard ---

test('XtSectionCard has title, badge, and toggleable props', () => {
  const src = source('../src/components/xt/XtSectionCard.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtSectionCard' \}\)/)
  assert.match(src, /title:/)
  assert.match(src, /badge:/)
  assert.match(src, /toggleable:/)
  assert.match(src, /defaultCollapsed:/)
})

test('XtSectionCard exposes collapsed state and toggle method', () => {
  const src = source('../src/components/xt/XtSectionCard.vue')
  assert.match(src, /defineExpose\(\{ collapsed, toggle \}\)/)
  assert.match(src, /xt-section-card--collapsed/)
})

test('XtSectionCard renders toolbar slot and toggle button', () => {
  const src = source('../src/components/xt/XtSectionCard.vue')
  assert.match(src, /slot name="toolbar"/)
  assert.match(src, /type="button"/)
  assert.match(src, /:aria-expanded="!collapsed"/)
  assert.match(src, /:aria-label="collapsed \? '展开区块' : '收起区块'"/)
  assert.match(src, /@click\.stop="toggle"/)
})

// --- XtDrawer ---

test('XtDrawer uses Teleport and Transition with v-model', () => {
  const src = source('../src/components/xt/XtDrawer.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtDrawer' \}\)/)
  assert.match(src, /Teleport to="body"/)
  assert.match(src, /modelValue:/)
  assert.match(src, /update:modelValue/)
})

test('XtDrawer supports side and size variants', () => {
  const src = source('../src/components/xt/XtDrawer.vue')
  assert.match(src, /left.*right/)
  assert.match(src, /narrow.*normal.*wide/)
  assert.match(src, /xt-drawer--right/)
  assert.match(src, /xt-drawer--left/)
})

test('XtDrawer has accessible close button and dialog role', () => {
  const src = source('../src/components/xt/XtDrawer.vue')
  assert.match(src, /role="dialog"/)
  assert.match(src, /aria-label/)
  assert.match(src, /aria-label="Close"/)
})

// --- XtKpiRibbon ---

test('XtKpiRibbon is a flex container with horizontal scroll', () => {
  const src = source('../src/components/xt/XtKpiRibbon.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtKpiRibbon' \}\)/)
  assert.match(src, /display: flex/)
  assert.match(src, /overflow-x: auto/)
  assert.match(src, /scrollbar-width: none/)
})

test('XtKpiRibbon uses role="list" for accessibility', () => {
  const src = source('../src/components/xt/XtKpiRibbon.vue')
  assert.match(src, /role="list"/)
})

test('XtKpiRibbon children get equal flex sizing', () => {
  const src = source('../src/components/xt/XtKpiRibbon.vue')
  assert.match(src, /flex: 1 1 0/)
  assert.match(src, /min-width: 160px/)
})
