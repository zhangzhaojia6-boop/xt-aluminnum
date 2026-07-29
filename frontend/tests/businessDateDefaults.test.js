import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  ownerDailyBusinessDateOptions,
  resolveRecentRequestedBusinessDate,
  resolveRequestedEntryField,
  resolveRequestedEntryFields,
  resolveOwnerDailyRequestedBusinessDate,
} from '../src/utils/shiftClock.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

function readSource(relativePath) {
  return readFileSync(resolve(root, relativePath), 'utf8')
}

test('business date defaults: manage pages use the 07:50 production anchor', () => {
  const files = [
    'src/views/manage/live/LiveDashboardPage.vue',
    'src/views/reports/LiveDashboard.vue',
    'src/views/reports/ReportList.vue',
    'src/views/attendance/AttendanceOverview.vue',
    'src/views/attendance/ExceptionList.vue',
    'src/components/manage/DateSwitcher.vue',
    'src/composables/useDateRange.js',
  ]

  for (const file of files) {
    const source = readSource(file)
    assert.match(source, /inferBusinessDate/, `${file} should use the production business day`)
    assert.doesNotMatch(source, /dayjs\(\)\.format\('YYYY-MM-DD'\)/, `${file} should not default to calendar today`)
  }
})

test('business date defaults: historical ledger pages use the last completed business day', () => {
  for (const file of [
    'src/views/energy/EnergyCenter.vue',
    'src/views/manage/fill-details/FillDetailsPage.vue',
  ]) {
    const source = readSource(file)
    assert.match(source, /inferLastCompletedBusinessDate/, `${file} should use the last completed business day`)
    assert.doesNotMatch(source, /dayjs\(\)\.format\('YYYY-MM-DD'\)/, `${file} should not default to calendar today`)
  }
})

test('business date defaults: owner daily pages use the 09:30 owner anchor', () => {
  const files = [
    'src/views/mobile/ConsumableEntry.vue',
    'src/views/mobile/MobileEntry.vue',
    'src/views/mobile/UnifiedEntryForm.vue',
  ]

  for (const file of files) {
    const source = readSource(file)
    assert.match(source, /inferOwnerDailyBusinessDate/, `${file} should use the owner daily business day`)
    assert.doesNotMatch(source, /dayjs\(\)\.format\('YYYY-MM-DD'\)/, `${file} should not default owner daily entries to calendar today`)
  }
})

test('owner daily backfill offers the current owner date and seven prior dates', () => {
  assert.deepEqual(ownerDailyBusinessDateOptions('2026-07-19'), [
    '2026-07-19',
    '2026-07-18',
    '2026-07-17',
    '2026-07-16',
    '2026-07-15',
    '2026-07-14',
    '2026-07-13',
    '2026-07-12',
  ])

  const source = readSource('src/views/mobile/UnifiedEntryForm.vue')
  assert.match(source, /v-model="ownerDailySelectedDate"/)
  assert.match(source, /loadOwnerDailyEntryForDate/)
})

test('owner daily fill accepts only an in-range business date from an alert link', () => {
  assert.equal(
    resolveOwnerDailyRequestedBusinessDate('2026-07-17', '2026-07-19'),
    '2026-07-17'
  )
  assert.equal(
    resolveOwnerDailyRequestedBusinessDate(['2026-07-18'], '2026-07-19'),
    '2026-07-18'
  )
  assert.equal(resolveOwnerDailyRequestedBusinessDate('2026-06-01', '2026-07-19'), '')
  assert.equal(resolveOwnerDailyRequestedBusinessDate('not-a-date', '2026-07-19'), '')

  const source = readSource('src/views/mobile/UnifiedEntryForm.vue')
  assert.match(source, /route\.query\.business_date/)
  assert.match(source, /resolveOwnerDailyRequestedBusinessDate/)
})

test('fact task fill accepts only a recent business date and applies it to shift forms', () => {
  assert.equal(
    resolveRecentRequestedBusinessDate('2026-07-17', '2026-07-19'),
    '2026-07-17'
  )
  assert.equal(resolveRecentRequestedBusinessDate('2026-07-20', '2026-07-19'), '')
  assert.equal(resolveRecentRequestedBusinessDate('2026-06-01', '2026-07-19'), '')
  assert.equal(resolveRecentRequestedBusinessDate('not-a-date', '2026-07-19'), '')

  const source = readSource('src/views/mobile/UnifiedEntryForm.vue')
  assert.match(source, /resolveRecentRequestedBusinessDate/)
  assert.match(source, /requestedTaskBusinessDate/)
  assert.match(source, /business_date:\s*requestedTaskBusinessDate/)
  assert.match(source, /补录任务日期无效或已超出可补录范围/)
})

test('requested entry field only resolves when the signed-in role can see it', () => {
  assert.equal(
    resolveRequestedEntryField('total_electricity_kwh', [
      { name: 'total_electricity_kwh' },
      { name: 'total_gas_m3' },
    ]),
    'total_electricity_kwh',
  )
  assert.equal(
    resolveRequestedEntryField(['park_inbound_daily'], [{ name: 'park_inbound_daily' }]),
    'park_inbound_daily',
  )
  assert.equal(resolveRequestedEntryField('total_cost_10k', [{ name: 'total_electricity_kwh' }]), '')
})

test('requested entry fields accept csv or repeated query values and keep only visible fields', () => {
  const fields = [
    { name: 'park_inbound_daily' },
    { name: 'new_plant_inbound_daily' },
  ]

  assert.deepEqual(
    resolveRequestedEntryFields('park_inbound_daily,new_plant_inbound_daily', fields),
    ['park_inbound_daily', 'new_plant_inbound_daily'],
  )
  assert.deepEqual(
    resolveRequestedEntryFields(
      ['new_plant_inbound_daily', 'hidden_field,park_inbound_daily', 'new_plant_inbound_daily'],
      fields,
    ),
    ['new_plant_inbound_daily', 'park_inbound_daily'],
  )
})

test('unified entry consumes all requested concrete form fields', () => {
  const source = readSource('src/views/mobile/UnifiedEntryForm.vue')

  assert.match(source, /route\.query\.entry_fields/)
  assert.match(source, /resolveRequestedEntryFields/)
  assert.match(source, /requestedEntryFields\.includes/)
  assert.match(source, /ue-field--requested/)
})

test('mobile entry landing separates owner daily hint from production shift hint', () => {
  const source = readSource('src/views/mobile/MobileEntry.vue')

  assert.match(source, /OWNER_DAILY_BUCKETS/)
  assert.match(source, /inferOwnerDailyBusinessDate/)
  assert.match(source, /每日一录/)
  assert.match(source, /按 09:30 起算/)
})

test('missing report compact mode stays small on yesterday report', () => {
  const source = readSource('src/components/manage/MissingReportPanel.vue')
  assert.match(source, /xt-missing-report__chips/)
  assert.match(source, /props\.rows\.slice\(0,\s*1\)/)
  assert.match(source, /compactOverflowCount/)
  assert.match(source, /compactRoleStats/)
  assert.match(source, /scrollbar-width:\s*none/)
})
