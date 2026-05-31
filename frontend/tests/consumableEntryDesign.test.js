import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/mobile/ConsumableEntry.vue', import.meta.url), 'utf8')
const apiSrc = readFileSync(new URL('../src/api/consumables.js', import.meta.url), 'utf8')

test('ConsumableEntry keeps the real daily consumables data path', () => {
  assert.match(src, /fetchConsumableWorkshops/)
  assert.match(src, /fetchDailyConsumableLog/)
  assert.match(src, /upsertDailyConsumableLog/)
  assert.match(apiSrc, /api\.get\(['"]\/consumables\/workshops['"]/)
  assert.match(apiSrc, /api\.get\(['"]\/consumables\/daily['"]/)
  assert.match(apiSrc, /api\.post\(['"]\/consumables\/daily['"]/)
})

test('ConsumableEntry preserves workshop date dynamic fields and save payload', () => {
  assert.match(src, /v-model="selectedWorkshopId"/)
  assert.match(src, /v-model="businessDate"/)
  assert.match(src, /v-for="\(\s*field,\s*index\s*\) in selectedWorkshop\.fields"/)
  assert.match(src, /v-model="formValues\[field\.name\]"/)
  assert.match(src, /:min="0"/)
  assert.match(src, /:precision="3"/)
  assert.match(src, /workshop_id:\s*selectedWorkshopId\.value/)
  assert.match(src, /business_date:\s*businessDate\.value/)
  assert.match(src, /payload/)
})

test('ConsumableEntry uses industrial blue command styling without purple drift', () => {
  for (const token of [
    'data-testid="consumable-entry"',
    'consumable-hub',
    'CONSUMABLE BAY',
    'CONTROL BAY',
    'WORKSHOP SIGNAL',
    'consumableSeq(index)',
    'saveStatusLabel',
    '#00f2ff',
    'consumableHubScan',
    'consumableHubLed',
    'consumableHubCardIn',
    'consumableHubButtonSweep',
    'prefers-reduced-motion',
    'bottom: calc(var(--xt-tabbar-height) + 14px + env(safe-area-inset-bottom, 0px))',
  ]) {
    assert.match(src, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(src, /purple|violet|lavender/i)
})
