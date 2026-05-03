import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('review task center is an exception supplement surface, not manual approval queue', () => {
  const review = source('../src/views/review/ReviewTaskCenter.vue')

  for (const retired of ['待审', '已审', '批量通过', '批量驳回', '审阅中心']) {
    assert.doesNotMatch(review, new RegExp(retired))
  }

  for (const expected of ['异常与补录', '缺报', '退回', '差异', '同步滞后']) {
    assert.match(review, new RegExp(expected))
  }

  assert.match(review, /reconciliation_open_count/)
  assert.match(review, /mes_sync_status/)
  assert.doesNotMatch(review, /\['submitted', 'reviewed', 'auto_confirmed'\]/)
})

test('shift center no longer exposes production shift import in the management path', () => {
  const shift = source('../src/views/shift/ShiftCenter.vue')

  assert.doesNotMatch(shift, /导入生产班次数据/)
  assert.doesNotMatch(shift, /importProductionFile/)
  assert.doesNotMatch(shift, /type="file"/)
  assert.match(shift, /班次配置/)
})
