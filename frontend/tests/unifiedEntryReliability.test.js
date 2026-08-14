import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildEntryRetryRecord,
  filterEntryGroups,
  isMeaningfulEntryDraft,
} from '../src/utils/unifiedEntryReliability.js'

test('filterEntryGroups only keeps fields requested by a targeted fill task', () => {
  const groups = [
    {
      label: '日报',
      fields: [
        { name: 'output_weight', label: '产量' },
        { name: 'electricity_daily', label: '电耗' },
      ],
    },
    {
      label: '备注',
      fields: [{ name: 'note', label: '备注' }],
    },
  ]

  assert.deepEqual(filterEntryGroups(groups, ['electricity_daily']), [
    {
      label: '日报',
      fields: [{ name: 'electricity_daily', label: '电耗' }],
    },
  ])
  assert.equal(filterEntryGroups(groups, []).length, 2)
})

test('filterEntryGroups keeps required dependencies for a valid targeted submission', () => {
  const groups = [{
    label: '逐卷',
    fields: [
      { name: 'tracking_card_no', required: true },
      { name: 'input_weight', required: true },
      { name: 'operator_notes', required: false },
    ],
  }]

  assert.deepEqual(
    filterEntryGroups(groups, ['operator_notes'], ['tracking_card_no', 'input_weight'])[0].fields.map((field) => field.name),
    ['tracking_card_no', 'input_weight', 'operator_notes'],
  )
})

test('buildEntryRetryRecord maps each submit target to one stable queued request', () => {
  const ownerRecord = buildEntryRetryRecord({
    submitTarget: 'owner_daily',
    payload: { business_date: '2026-08-14', data: { total_electricity_kwh: 1200 } },
    draftKey: 'draft:owner:2026-08-14',
  })
  const shiftRecord = buildEntryRetryRecord({
    submitTarget: 'shift_report',
    payload: { business_date: '2026-08-14', shift_id: 3 },
    draftKey: 'draft:shift:2026-08-14:3',
  })

  assert.deepEqual(ownerRecord, {
    type: 'http',
    method: 'post',
    url: '/mobile/owner-daily',
    body: { business_date: '2026-08-14', data: { total_electricity_kwh: 1200 } },
    dedupeKey: 'unified-entry:owner_daily:draft:owner:2026-08-14',
    clearDraftKey: 'draft:owner:2026-08-14',
  })
  assert.equal(shiftRecord.url, '/mobile/report/submit')
  assert.equal(shiftRecord.dedupeKey, 'unified-entry:shift_report:draft:shift:2026-08-14:3')
})

test('buildEntryRetryRecord rejects an unsupported submit target', () => {
  assert.throws(
    () => buildEntryRetryRecord({ submitTarget: 'unknown', payload: {}, draftKey: 'draft:key' }),
    /unsupported submit target/,
  )
})

test('isMeaningfulEntryDraft ignores an empty initialized form', () => {
  assert.equal(isMeaningfulEntryDraft({ form: { output_weight: null, note: '' } }), false)
  assert.equal(isMeaningfulEntryDraft({ form: { output_weight: 0, note: '' } }), true)
  assert.equal(isMeaningfulEntryDraft({ form: { machine_stop_records: [{ downtime_minutes: null }] } }), false)
  assert.equal(isMeaningfulEntryDraft({ form: { machine_stop_records: [{ downtime_minutes: 30 }] } }), true)
})
