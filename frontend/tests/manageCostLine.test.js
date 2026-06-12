import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('CostLine renders configurable cost label + 口径：估算 with required test-id', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.match(src, /data-testid="manage-cost-line"/)
  assert.match(src, /costLabel/)
  assert.match(src, /今日估算成本/)
  assert.match(src, /口径：估算/)
})

test('CostLine divides estimated_cost by 10000 and trims trailing zero decimals', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.match(src, /\/\s*10000/)
  assert.match(src, /formatNumber\(Number\(props\.estimate\.estimated_cost\) \/ 10000,\s*2\)/)
})

test('CostLine mutes when estimate_ready is false or estimated_cost null', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.match(src, /!props\.estimate\?\.estimate_ready/)
  assert.match(src, /props\.estimate\?\.estimated_cost\s*==\s*null/)
  assert.match(src, /'is-muted':\s*muted/)
  assert.match(src, /return '—'/)
})

test('CostLine does NOT split into electricity / gas (no such fields)', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.equal(/electricity/i.test(src), false)
  assert.equal(/gas[_\s]?cost/i.test(src), false)
  assert.equal(/电费|气费/.test(src), false)
})

test('CostLine tooltip uses Chinese ton unit', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.match(src, /产量 \$\{row\.tons \|\| 0\} 吨/)
  assert.doesNotMatch(src, /产量 \$\{row\.tons \|\| 0\} t/)
})

test('CostLine uses --xt-* tokens, no hex colors', () => {
  const src = source('../src/components/manage/CostLine.vue')
  assert.match(src, /var\(--xt-bg-panel\)/)
  assert.match(src, /var\(--xt-border\)/)
  const styleBlock = src.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(styleBlock), false)
})
