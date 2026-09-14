import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mapWorkshopRows } from '../src/components/manage/_workshopRows.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('workshop ranking preserves missing output separately from confirmed zero', () => {
  const rows = [
    { workshop_name: 'A', total_output: 5, target_value: 8 },
    { workshop_name: 'B', total_output: 12, target_value: 10 },
    { workshop_name: 'C', total_output: null, target_value: null },
    { workshop_name: 'D', total_output: 0, target_value: 0 }
  ]
  const out = mapWorkshopRows(rows)
  assert.deepEqual(out.map((r) => r.name), ['B', 'A', 'D', 'C'])
  assert.equal(out[0].today, 12)
  assert.equal(out[0].monthAvg, 10)
  assert.equal(out[2].today, 0)
  assert.equal(out[3].today, null)
  assert.equal(out[3].monthAvg, null)
})

test('mapWorkshopRows handles empty / null input', () => {
  assert.deepEqual(mapWorkshopRows([]), [])
  assert.deepEqual(mapWorkshopRows(null), [])
  assert.deepEqual(mapWorkshopRows(undefined), [])
})

test('mapWorkshopRows defaults missing workshop_name to "-"', () => {
  const out = mapWorkshopRows([{ total_output: 1, target_value: 0 }])
  assert.equal(out[0].name, '-')
})

test('WorkshopBarChart imports mapWorkshopRows from sibling module', () => {
  const src = source('../src/components/manage/WorkshopBarChart.vue')
  assert.match(src, /from\s+['"]\.\/_workshopRows\.js['"]/)
  assert.match(src, /data-testid="manage-workshop-bar"/)
  assert.match(src, /VChart/)
})

test('WorkshopBarChart uses --xt-* tokens for container, not echarts colors', () => {
  const src = source('../src/components/manage/WorkshopBarChart.vue')
  assert.match(src, /var\(--xt-bg-panel\)/)
  assert.match(src, /var\(--xt-border\)/)
})

test('WorkshopBarChart labels the selected day and monthly daily average', () => {
  const src = source('../src/components/manage/WorkshopBarChart.vue')
  assert.match(src, /'所选日'/)
  assert.match(src, /'月日均'/)
  assert.doesNotMatch(src, /月累/)
})
