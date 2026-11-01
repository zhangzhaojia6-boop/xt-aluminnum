import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue', import.meta.url), 'utf8')

test('workshop dashboard shows missing numbers as a dash, not 0', () => {
  // Number(null) 是 0：接口给空值时不能显示成 0
  assert.match(src, /function formatNumber\(value, digits = 2\) \{\s*if \(value === null \|\| value === undefined \|\| value === ''\) return '-'/)
})

test('workshop dashboard drops the unit when a KPI value is missing', () => {
  assert.match(src, /\.map\(\(item\) => \(item\.value === '-' \? \{ \.\.\.item, unit: '' \} : item\)\)/)
})

test('workshop dashboard leaves out the coil count the MES WIP report does not have', () => {
  assert.match(src, /row\.doing_count == null \? '' : `\$\{formatNumber\(row\.doing_count, 0\)\} 卷`/)
})
