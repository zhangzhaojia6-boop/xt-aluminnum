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

// --- XtTrendSpark ---

// --- XtCommandBar ---

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
  assert.match(src, /--xt-danger/)
  assert.match(src, /xt-border-danger/)
})

test('XtErrorPanel emits retry event', () => {
  const src = source('../src/components/xt/XtErrorPanel.vue')
  assert.match(src, /\$emit\('retry'\)/)
  assert.match(src, /defineEmits\(\['retry'\]\)/)
})

// --- XtAppShell ---

// --- XtDateRangePicker ---

// --- XtNumericInput ---

// --- XtShiftPicker ---

// --- XtUnitSelect ---
