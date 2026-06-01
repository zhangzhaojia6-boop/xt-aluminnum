import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildFactorySourceStrip } from '../src/utils/factorySourceStrip.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('buildFactorySourceStrip renders MES extended source and separates tonnage bases', () => {
  const strip = buildFactorySourceStrip({
    source: 'mes_extended',
    freshness: { status: 'fresh', source: 'mes_extended' },
    today_output_tons: 6.2,
    total_output_tons: 18.5,
    wip_tons: 13.5,
    yield_rate: 92.5,
  })

  assert.equal(strip.sourceLabel, 'MES 扩展数据')
  assert.equal(strip.tone, 'success')
  assert.deepEqual(strip.items, [
    { key: 'inbound', label: '入库产量', value: '6.2', unit: '吨' },
    { key: 'process', label: '过站下机', value: '18.5', unit: '吨' },
    { key: 'wip', label: '在制', value: '13.5', unit: '吨' },
    { key: 'yield', label: '成品率', value: '92.5', unit: '%' },
  ])
})

test('buildFactorySourceStrip does not invent zero values when source fields are missing', () => {
  const strip = buildFactorySourceStrip({
    source: 'mes_extended',
    freshness: { status: 'fresh' },
  })

  assert.equal(strip.items[0].value, '—')
  assert.equal(strip.items[1].value, '—')
  assert.equal(strip.items[2].value, '—')
  assert.equal(strip.items[3].value, '—')
})

test('FactorySourceStrip keeps Stitch cyber-industrial structure without changing data props', () => {
  const src = source('../src/components/manage/FactorySourceStrip.vue')

  assert.match(src, /data-testid="factory-source-strip"/)
  assert.match(src, /xt-source-strip__scan/)
  assert.match(src, /xt-source-strip__rail/)
  assert.match(src, /backdrop-filter/)
  assert.match(src, /xt-source-strip-reveal/)
  assert.match(src, /buildFactorySourceStrip\(props\.overview\)/)
})

test('FactorySourceStrip aligns with site theme tokens instead of standalone colors', () => {
  const src = source('../src/components/manage/FactorySourceStrip.vue')
  const styleBlock = src.split('<style')[1] || ''

  assert.equal(/#[0-9a-fA-F]{3,8}/.test(styleBlock), false)
  assert.equal(/rgba\(/.test(styleBlock), false)
  assert.match(styleBlock, /var\(--xt-bg-ink-panel\) 86%, var\(--xt-bg-panel\)/)
  assert.match(styleBlock, /var\(--xt-radius-xl\)/)
  assert.match(styleBlock, /var\(--xt-font-number\)/)
  assert.match(styleBlock, /prefers-reduced-motion/)
})
