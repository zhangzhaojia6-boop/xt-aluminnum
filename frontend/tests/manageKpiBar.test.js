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

test('KpiBar uses the Stitch industrial blue card surface without heavy effects', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  const styleBlock = src.split('<style')[1] || ''
  assert.match(styleBlock, /rgba\(70,\s*157,\s*238,\s*0\.26\)/)
  assert.match(styleBlock, /linear-gradient\(180deg,\s*rgba\(18,\s*57,\s*88,\s*0\.68\)/)
  assert.match(styleBlock, /var\(--xt-font-number\)/)
  assert.doesNotMatch(styleBlock, /animation:\s*[^;{}]*infinite/)
  assert.doesNotMatch(styleBlock, /backdrop-filter|filter:\s*blur/i)
})

test('KpiBar lays out dashboard-width KPI cards with mobile breakpoints', () => {
  const src = source('../src/components/manage/KpiBar.vue')
  assert.match(src, /grid-template-columns:\s*repeat\(6,\s*minmax\(0,\s*1fr\)\)/)
  assert.match(src, /@media\s*\(max-width:\s*1180px\)/)
  assert.match(src, /grid-template-columns:\s*repeat\(3,\s*1fr\)/)
  assert.match(src, /@media\s*\(max-width:\s*720px\)/)
  assert.match(src, /grid-template-columns:\s*repeat\(2,\s*1fr\)/)
})
