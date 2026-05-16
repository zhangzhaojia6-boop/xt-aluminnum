import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const modelFile = resolve('..', 'backend', 'app', 'models', 'production.py')

test('WorkOrderEntry has UNIQUE dedup constraint on (work_order_id, shift_id, business_date)', () => {
  const src = readFileSync(modelFile, 'utf8')
  assert.match(src, /uq_work_order_entries_dedup/)
  assert.match(src, /UniqueConstraint\(\s*'work_order_id',\s*'shift_id',\s*'business_date'/)
})

test('WorkOrder tracking_card_no has unique=True', () => {
  const src = readFileSync(modelFile, 'utf8')
  assert.match(src, /tracking_card_no.*unique=True/)
})

test('MobileShiftReport has composite unique constraint', () => {
  const src = readFileSync(modelFile, 'utf8')
  assert.match(src, /uq_mobile_shift_reports_key/)
  assert.match(src, /'business_date',\s*'shift_config_id',\s*'workshop_id',\s*'team_id'/)
})
