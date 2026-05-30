import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

// --- XtBarChart ---

test('XtBarChart registers echarts modules and accepts series/xLabels', () => {
  const src = source('../src/components/xt/XtBarChart.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtBarChart' \}\)/)
  assert.match(src, /series:/)
  assert.match(src, /xLabels:/)
  assert.match(src, /CanvasRenderer/)
  assert.match(src, /BarChart/)
  assert.match(src, /VChart/)
})

test('XtBarChart supports stacked and horizontal modes', () => {
  const src = source('../src/components/xt/XtBarChart.vue')
  assert.match(src, /stacked:/)
  assert.match(src, /horizontal:/)
  assert.match(src, /stack.*total/)
})

test('XtBarChart applies color palette to series', () => {
  const src = source('../src/components/xt/XtBarChart.vue')
  assert.match(src, /PALETTE/)
  assert.match(src, /#1f6feb/)
  assert.match(src, /s\.color \|\| PALETTE/)
})

// --- XtGaugeChart ---

test('XtGaugeChart registers gauge module and accepts value/max/label', () => {
  const src = source('../src/components/xt/XtGaugeChart.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtGaugeChart' \}\)/)
  assert.match(src, /value:/)
  assert.match(src, /max:/)
  assert.match(src, /label:/)
  assert.match(src, /GaugeChart/)
  assert.match(src, /VChart/)
})

test('XtGaugeChart supports thresholds and unit props', () => {
  const src = source('../src/components/xt/XtGaugeChart.vue')
  assert.match(src, /thresholds:/)
  assert.match(src, /unit:/)
  assert.match(src, /#cf222e/)
  assert.match(src, /#2da44e/)
})

test('XtGaugeChart uses tabular-nums for value display', () => {
  const src = source('../src/components/xt/XtGaugeChart.vue')
  assert.match(src, /tnum/)
  assert.match(src, /valueAnimation: true/)
})

// --- XtTrendSpark ---

test('XtTrendSpark is a minimal sparkline with no axes', () => {
  const src = source('../src/components/xt/XtTrendSpark.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtTrendSpark' \}\)/)
  assert.match(src, /data:/)
  assert.match(src, /show: false/)
  assert.match(src, /symbol: 'none'/)
})

test('XtTrendSpark supports color/width/height props', () => {
  const src = source('../src/components/xt/XtTrendSpark.vue')
  assert.match(src, /color:/)
  assert.match(src, /width:/)
  assert.match(src, /height:/)
  assert.match(src, /120px/)
  assert.match(src, /32px/)
})

test('XtTrendSpark renders area fill with low opacity', () => {
  const src = source('../src/components/xt/XtTrendSpark.vue')
  assert.match(src, /areaStyle/)
  assert.match(src, /opacity: 0\.08/)
})

// --- XtCommandBar ---

test('XtCommandBar has date range picker and export button', () => {
  const src = source('../src/components/xt/XtCommandBar.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtCommandBar' \}\)/)
  assert.match(src, /el-date-picker/)
  assert.match(src, /exportable:/)
  assert.match(src, /xt-command-bar__export/)
})

test('XtCommandBar provides date shortcuts', () => {
  const src = source('../src/components/xt/XtCommandBar.vue')
  assert.match(src, /今日/)
  assert.match(src, /昨日/)
  assert.match(src, /本周/)
  assert.match(src, /本月/)
  assert.match(src, /近7天/)
  assert.match(src, /近30天/)
})

test('XtCommandBar has prefix and filters slots', () => {
  const src = source('../src/components/xt/XtCommandBar.vue')
  assert.match(src, /slot name="prefix"/)
  assert.match(src, /slot name="filters"/)
})

// --- XtErrorPanel ---

test('XtErrorPanel displays error message with retry button', () => {
  const src = source('../src/components/xt/XtErrorPanel.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtErrorPanel' \}\)/)
  assert.match(src, /message:/)
  assert.match(src, /retryable:/)
  assert.match(src, /role="alert"/)
})

test('XtErrorPanel has danger styling', () => {
  const src = source('../src/components/xt/XtErrorPanel.vue')
  assert.match(src, /xt-bg-danger/)
  assert.match(src, /xt-border-danger/)
})

test('XtErrorPanel emits retry event', () => {
  const src = source('../src/components/xt/XtErrorPanel.vue')
  assert.match(src, /\$emit\('retry'\)/)
  assert.match(src, /defineEmits\(\['retry'\]\)/)
})

// --- XtAppShell ---

test('XtAppShell provides four layout slots', () => {
  const src = source('../src/components/xt/XtAppShell.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtAppShell' \}\)/)
  assert.match(src, /slot name="left"/)
  assert.match(src, /slot name="top"/)
  assert.match(src, /slot name="drawer"/)
  assert.match(src, /xt-app-shell__main/)
})

test('XtAppShell uses flex layout with 100vh', () => {
  const src = source('../src/components/xt/XtAppShell.vue')
  assert.match(src, /display: flex/)
  assert.match(src, /height: 100vh/)
})

test('XtAppShell sidebar and drawer have configurable widths', () => {
  const src = source('../src/components/xt/XtAppShell.vue')
  assert.match(src, /--xt-shell-sidebar-width/)
  assert.match(src, /--xt-shell-drawer-width/)
  assert.match(src, /420px/)
})

// --- XtDateRangePicker ---

test('XtDateRangePicker wraps el-date-picker with shortcuts', () => {
  const src = source('../src/components/xt/XtDateRangePicker.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtDateRangePicker' \}\)/)
  assert.match(src, /el-date-picker/)
  assert.match(src, /type="daterange"/)
  assert.match(src, /shortcuts/)
})

test('XtDateRangePicker has 8 preset shortcuts', () => {
  const src = source('../src/components/xt/XtDateRangePicker.vue')
  assert.match(src, /今日/)
  assert.match(src, /昨日/)
  assert.match(src, /本周/)
  assert.match(src, /本月/)
  assert.match(src, /本季/)
  assert.match(src, /本年/)
  assert.match(src, /近7天/)
  assert.match(src, /近30天/)
})

test('XtDateRangePicker uses v-model pattern', () => {
  const src = source('../src/components/xt/XtDateRangePicker.vue')
  assert.match(src, /modelValue:/)
  assert.match(src, /update:modelValue/)
})

// --- XtNumericInput ---

test('XtNumericInput has numeric inputmode and unit suffix', () => {
  const src = source('../src/components/xt/XtNumericInput.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtNumericInput' \}\)/)
  assert.match(src, /inputmode="decimal"/)
  assert.match(src, /unit:/)
  assert.match(src, /xt-numeric-input__unit/)
})

test('XtNumericInput supports min/max/precision', () => {
  const src = source('../src/components/xt/XtNumericInput.vue')
  assert.match(src, /min:/)
  assert.match(src, /max:/)
  assert.match(src, /precision:/)
  assert.match(src, /toFixed/)
})

test('XtNumericInput uses tabular-nums', () => {
  const src = source('../src/components/xt/XtNumericInput.vue')
  assert.match(src, /font-feature-settings: "tnum"/)
})

// --- XtShiftPicker ---

test('XtShiftPicker renders shift options with v-model', () => {
  const src = source('../src/components/xt/XtShiftPicker.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtShiftPicker' \}\)/)
  assert.match(src, /modelValue:/)
  assert.match(src, /shifts:/)
  assert.match(src, /el-select/)
  assert.match(src, /el-option/)
})

test('XtShiftPicker has default three shifts', () => {
  const src = source('../src/components/xt/XtShiftPicker.vue')
  assert.match(src, /大夜/)
  assert.match(src, /长白班/)
  assert.match(src, /小夜/)
})

test('XtShiftPicker supports disabled state', () => {
  const src = source('../src/components/xt/XtShiftPicker.vue')
  assert.match(src, /disabled:/)
  assert.match(src, /:disabled="disabled"/)
})

// --- XtUnitSelect ---

test('XtUnitSelect renders unit options with v-model', () => {
  const src = source('../src/components/xt/XtUnitSelect.vue')
  assert.match(src, /defineOptions\(\{ name: 'XtUnitSelect' \}\)/)
  assert.match(src, /modelValue:/)
  assert.match(src, /units:/)
  assert.match(src, /el-select/)
  assert.match(src, /el-option/)
})

test('XtUnitSelect has default measurement units', () => {
  const src = source('../src/components/xt/XtUnitSelect.vue')
  assert.match(src, /吨/)
  assert.match(src, /千克/)
  assert.match(src, /ton/)
  assert.match(src, /kg/)
})

test('XtUnitSelect supports disabled state', () => {
  const src = source('../src/components/xt/XtUnitSelect.vue')
  assert.match(src, /disabled:/)
  assert.match(src, /:disabled="disabled"/)
})
