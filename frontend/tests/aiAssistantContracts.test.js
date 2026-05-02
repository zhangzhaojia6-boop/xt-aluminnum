import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeAssistantAnswer,
  normalizeBriefing,
  normalizeWatchlistItem
} from '../src/utils/aiAssistantContracts.js'

test('answer normalization always returns assistant answer contract', () => {
  const answer = normalizeAssistantAnswer({
    answer: '先看冷轧 1#。',
    confidence: 'high',
    evidence_refs: [{ kind: 'machine', key: '冷轧:01' }],
    missing_data: ['cost_inputs'],
    recommended_next_actions: ['查看证据'],
    can_create_watch: true
  })

  assert.equal(answer.answer, '先看冷轧 1#。')
  assert.equal(answer.confidence, 'high')
  assert.equal(answer.evidenceRefs.length, 1)
  assert.deepEqual(answer.missingData, ['cost_inputs'])
  assert.deepEqual(answer.recommendedNextActions, ['查看证据'])
  assert.equal(answer.canCreateWatch, true)
})

test('briefing normalization preserves states and evidence count', () => {
  const briefing = normalizeBriefing({
    id: 'brief-1',
    severity: 'warning',
    read: true,
    follow_up_status: 'followed',
    payload: { rules_fired: [{ evidence_refs: [{ key: 'A' }, { key: 'B' }] }] },
    expires_at: '2026-05-02T09:00:00+08:00'
  })

  assert.equal(briefing.id, 'brief-1')
  assert.equal(briefing.severity, 'warning')
  assert.equal(briefing.read, true)
  assert.equal(briefing.followUpStatus, 'followed')
  assert.equal(briefing.evidenceCount, 2)
  assert.equal(briefing.expiresAt, '2026-05-02T09:00:00+08:00')
})

test('watchlist normalization preserves scope and delivery settings', () => {
  const watch = normalizeWatchlistItem({
    id: 'watch-1',
    watch_type: 'machine',
    scope_key: '冷轧:01',
    trigger_rules: ['delay_hours_high'],
    quiet_hours: { start: '22:00', end: '07:00' },
    frequency: 'hourly',
    channels: ['in_app'],
    active: false
  })

  assert.equal(watch.type, 'machine')
  assert.equal(watch.scopeKey, '冷轧:01')
  assert.deepEqual(watch.triggerRules, ['delay_hours_high'])
  assert.deepEqual(watch.quietHours, { start: '22:00', end: '07:00' })
  assert.equal(watch.frequency, 'hourly')
  assert.deepEqual(watch.channels, ['in_app'])
  assert.equal(watch.active, false)
})
