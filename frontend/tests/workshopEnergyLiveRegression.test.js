import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  ACTIVE_WORKSHOP_NAMES,
  filterActiveWorkshopRows,
  normalizeWorkshopName,
} from '../src/utils/activeWorkshops.js'
import { buildLiveTickerItems, formatTrustedMetric } from '../src/utils/liveDashboardPhase2.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('active production workshop list is thirteen and keeps storage out of production filters', () => {
  assert.equal(ACTIVE_WORKSHOP_NAMES.length, 13)
  assert.equal(normalizeWorkshopName('铸轧二'), '铸二')
  assert.equal(normalizeWorkshopName('园区淬火'), '淬火车间')

  const rows = filterActiveWorkshopRows([
    { name: '铸轧二', is_active: true },
    { name: '成品库', is_active: true },
    { name: '铸轧五', is_active: true },
    { name: '冷轧三车间', is_active: false },
  ])

  assert.deepEqual(rows.map((row) => row.name), ['铸二'])
})

test('live metrics keep real zero but do not turn missing source data into fake zero', () => {
  assert.equal(formatTrustedMetric(null, '吨'), '待同步')
  assert.equal(formatTrustedMetric(undefined, 'kWh'), '待同步')
  assert.equal(formatTrustedMetric(0, '吨'), '0 吨')

  const items = buildLiveTickerItems({
    factory_total: {},
    energy_summary: { data_available: false },
    overall_progress: {},
    mes_sync_status: {},
  })

  assert.deepEqual(items.map((item) => item.value), [
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
    '待同步',
  ])
})

test('management pages use the last completed business day for historical ledgers', () => {
  const fillDetails = source('../src/views/manage/fill-details/FillDetailsPage.vue')
  const energy = source('../src/views/energy/EnergyCenter.vue')

  assert.match(fillDetails, /inferLastCompletedBusinessDate/)
  assert.match(energy, /inferLastCompletedBusinessDate/)
  assert.doesNotMatch(fillDetails, /const targetDate = ref\(inferBusinessDate\(\)\)/)
  assert.doesNotMatch(energy, /business_date: inferBusinessDate\(\)/)
})

test('entry surface permission is preserved for non-mobile admin users', () => {
  const authStore = source('../src/stores/auth.js')

  assert.match(authStore, /entry_surface: Boolean\(user\.entry_surface\) \|\| Boolean\(user\.is_mobile_user\)/)
  assert.match(authStore, /return this\.isMobileUser \|\| Boolean\(this\.user\?\.entry_surface\)/)
})
