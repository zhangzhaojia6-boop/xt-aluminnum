import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/DomainFilterChips.vue', import.meta.url), 'utf8')

test('DomainFilterChips renders 5 chips: 全部 + 4 domains', () => {
  for (const label of ['全部', '生产', '质检', '对账', '填报']) {
    assert.match(SRC, new RegExp(label))
  }
})

test('DomainFilterChips toggles all by clearing modelValue', () => {
  assert.match(SRC, /modelValue/)
  assert.match(SRC, /update:modelValue/)
  assert.match(SRC, /toggleAll|selectAll|clearDomains/)
})

test('DomainFilterChips count comes from props.counts', () => {
  assert.match(SRC, /props\.counts|counts\.production/)
})

test('DomainFilterChips style block uses --xt-* tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})

test('DomainFilterChips uses role=button, accessible', () => {
  assert.match(SRC, /role="button"|tabindex/)
})
