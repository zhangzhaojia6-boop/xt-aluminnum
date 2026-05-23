import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mapWorkshopRows } from '../src/components/manage/_workshopRows.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('mapWorkshopRows sorts by today desc, keeps name/today/compare', () => {
  const rows = [
    { workshop_name: 'A', total_output: 5, compare_value: 100 },
    { workshop_name: 'B', total_output: 12, compare_value: 80 },
    { workshop_name: 'C', total_output: null, compare_value: 60 }
  ]
  const out = mapWorkshopRows(rows)
  assert.deepEqual(out.map((r) => r.name), ['B', 'A', 'C'])
  assert.equal(out[0].today, 12)
  assert.equal(out[2].today, 0)
  assert.equal(out[2].compare, 60)
})

test('mapWorkshopRows handles empty / null input', () => {
  assert.deepEqual(mapWorkshopRows([]), [])
  assert.deepEqual(mapWorkshopRows(null), [])
  assert.deepEqual(mapWorkshopRows(undefined), [])
})

test('mapWorkshopRows defaults missing workshop_name to "-"', () => {
  const out = mapWorkshopRows([{ total_output: 1, compare_value: 0 }])
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

test('WorkshopBarChart legend names match plan: 今日 + 月累参考', () => {
  const src = source('../src/components/manage/WorkshopBarChart.vue')
  assert.match(src, /'今日'/)
  assert.match(src, /'月累参考'/)
})
