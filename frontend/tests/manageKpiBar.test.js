import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('KpiBar declares items prop and renders cards via v-for', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /defineProps\(\{\s*items:/)
  assert.match(src, /v-for="item in items"/)
  assert.match(src, /data-testid="kpi-card"/)
  assert.match(src, /data-testid="manage-kpi-bar"/)
})

test('KpiBar binds label / value / unit / hint slots', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /\{\{\s*item\.label\s*\}\}/)
  assert.match(src, /\{\{\s*item\.value\s*\}\}/)
  assert.match(src, /\{\{\s*item\.unit\s*\}\}/)
  assert.match(src, /\{\{\s*item\.hint\s*\}\}/)
})

test('KpiBar applies status and tone modifier classes', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /is-\$\{item\.status\}/)
  assert.match(src, /tone-\$\{item\.tone\}/)
  assert.match(src, /\.is-muted/)
  assert.match(src, /\.tone-positive/)
  assert.match(src, /\.tone-negative/)
})

test('KpiBar uses --xt-* tokens, not hardcoded colors/spacing', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /var\(--xt-bg-panel\)/)
  assert.match(src, /var\(--xt-border\)/)
  assert.match(src, /var\(--xt-text\)/)
  const styleBlock = src.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(styleBlock), false, 'no hex colors allowed')
})

test('KpiBar lays out 5 columns on desktop with mobile breakpoint', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /grid-template-columns:\s*repeat\(5,\s*1fr\)/)
  assert.match(src, /@media\s*\(max-width:\s*720px\)/)
  assert.match(src, /grid-template-columns:\s*repeat\(3,\s*1fr\)/)
})
