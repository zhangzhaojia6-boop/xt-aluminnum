import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('review task center is an exception supplement surface, not manual approval queue', () => {
  const review = source('../src/views/review/ReviewTaskCenter.vue')
  const realtimeApi = source('../src/api/realtime.js')

  for (const retired of ['待审', '已审', '批量通过', '批量驳回', '审阅中心']) {
    assert.doesNotMatch(review, new RegExp(retired))
  }

  for (const expected of ['异常与补录', '缺报', '退回', '差异', '同步滞后']) {
    assert.match(review, new RegExp(expected))
  }

  assert.match(review, /reconciliation_open_count/)
  assert.match(review, /const reconciliationOpenCount = computed/)
  assert.match(review, /const diffCount = reconciliationOpenCount/)
  assert.match(review, /mes_sync_status/)
  assert.match(review, /fetchLiveActiveDate/)
  assert.match(review, /initializeActiveBusinessDate/)
  assert.match(review, /fetchPendingAssignmentEntries/)
  assert.match(review, /待归属/)
  assert.match(review, /录入来源/)
  assert.match(review, /归属线索/)
  assert.match(review, /pendingAssignmentTasks/)
  assert.match(review, /created_by_user_name/)
  assert.match(review, /mes_match_count/)
  assert.match(review, /machine_candidate_count/)
  assert.match(review, /formatAssignmentSource/)
  assert.match(review, /formatAssignmentHint/)
  assert.match(review, /executeAssistantAction/)
  assert.match(review, /promote_draft_entry/)
  assert.match(review, /canPromotePendingAssignment/)
  assert.match(review, /normalizeMachineCandidates/)
  assert.match(review, /selectedMachineByEntry/)
  assert.match(review, /resolvePromoteMachineId/)
  assert.match(review, /machine_candidates/)
  assert.match(review, /选择机列/)
  assert.match(review, /绑定入账/)
  assert.match(review, /随行卡/)
  assert.match(review, /产出/)
  assert.match(review, /缺失字段/)
  assert.doesNotMatch(review, /\['submitted', 'reviewed', 'auto_confirmed'\]/)
  assert.doesNotMatch(review, /自动归属|一键归属/)
  assert.match(realtimeApi, /fetchLiveActiveDate/)
  assert.match(realtimeApi, /fetchPendingAssignmentEntries/)
  assert.match(realtimeApi, /\/aggregation\/live\/pending-assignment/)
})

test('shift center no longer exposes production shift import in the management path', () => {
  const shift = source('../src/views/shift/ShiftCenter.vue')

  assert.doesNotMatch(shift, /导入生产班次数据/)
  assert.doesNotMatch(shift, /importProductionFile/)
  assert.doesNotMatch(shift, /type="file"/)
  assert.match(shift, /班次配置/)
})
