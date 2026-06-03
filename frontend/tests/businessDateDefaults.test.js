import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

function readSource(relativePath) {
  return readFileSync(resolve(root, relativePath), 'utf8')
}

test('business date defaults: manage pages use the 07:30 production anchor', () => {
  const files = [
    'src/views/manage/live/LiveDashboardPage.vue',
    'src/views/reports/LiveDashboard.vue',
    'src/views/reports/ReportList.vue',
    'src/views/energy/EnergyCenter.vue',
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

test('business date defaults: owner daily pages use the 10:00 owner anchor', () => {
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

test('mobile entry landing separates owner daily hint from production shift hint', () => {
  const source = readSource('src/views/mobile/MobileEntry.vue')

  assert.match(source, /OWNER_DAILY_BUCKETS/)
  assert.match(source, /inferOwnerDailyBusinessDate/)
  assert.match(source, /每日一录/)
  assert.match(source, /按 10:00 起算/)
})

test('missing report compact mode stays small on yesterday report', () => {
  const source = readSource('src/components/manage/MissingReportPanel.vue')
  assert.match(source, /xt-missing-report__chips/)
  assert.match(source, /props\.rows\.slice\(0,\s*1\)/)
  assert.match(source, /compactOverflowCount/)
  assert.match(source, /compactRoleStats/)
  assert.match(source, /scrollbar-width:\s*none/)
})
