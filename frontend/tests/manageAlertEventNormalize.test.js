import test from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeFactoryDirector,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../src/components/manage/_alertEventNormalize.js'

const DATE = '2026-05-19'

test('normalizeFactoryDirector maps recent_items to production domain', () => {
  const payload = {
    exception_lane: {
      recent_items: [
        { id: 'p1', occurred_at: '2026-05-19T10:23:00', summary: '一车间产量异常' }
      ]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out.length, 1)
  assert.equal(out[0].id, 'production:p1')
  assert.equal(out[0].domain, 'production')
  assert.equal(out[0].summary, '一车间产量异常')
  assert.equal(out[0].occurredAt, '2026-05-19T10:23:00')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=anomaly')
  assert.equal(out[0].status, 'open')
})

test('normalizeFactoryDirector merges returned_items + reminder_items into reporting', () => {
  const payload = {
    exception_lane: {
      returned_items: [{ id: 'r1', summary: '退回' }],
      reminder_items: [{ id: 'm1', summary: '催报' }]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out.length, 2)
  assert.ok(out.every((e) => e.domain === 'reporting'))
})

test('normalizeFactoryDirector falls back to target_date midnight when occurred_at missing', () => {
  const payload = {
    exception_lane: { recent_items: [{ id: 'p1', summary: 'x' }] }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out[0].occurredAt, '2026-05-19T00:00:00')
})

test('normalizeFactoryDirector composes summary from workshop+shift+desc when missing', () => {
  const payload = {
    exception_lane: {
      recent_items: [{ id: 'p1', workshop_name: '一车间', shift_label: '早班', event_type: '产量异常' }]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out[0].summary, '一车间 早班 产量异常')
})

test('normalizeFactoryDirector handles null exception_lane safely', () => {
  assert.deepEqual(normalizeFactoryDirector({}, DATE), [])
  assert.deepEqual(normalizeFactoryDirector({ exception_lane: null }, DATE), [])
  assert.deepEqual(normalizeFactoryDirector(null, DATE), [])
})

test('normalizeFactoryDirector resolved status maps from row.status', () => {
  const payload = {
    exception_lane: { recent_items: [{ id: 'p1', summary: 'x', status: 'resolved' }] }
  }
  assert.equal(normalizeFactoryDirector(payload, DATE)[0].status, 'resolved')
})

test('normalizeQuality maps to quality domain with quality detail route', () => {
  const items = [{ id: 'q1', summary: '抽检不合格', occurred_at: '2026-05-19T11:00:00' }]
  const out = normalizeQuality(items, DATE)
  assert.equal(out[0].id, 'quality:q1')
  assert.equal(out[0].domain, 'quality')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=quality')
})

test('normalizeReconciliation maps to reconciliation domain', () => {
  const items = [{ id: 'r1', summary: '过磅差异', occurred_at: '2026-05-19T09:50:00' }]
  const out = normalizeReconciliation(items, DATE)
  assert.equal(out[0].domain, 'reconciliation')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=reconciliation')
})

test('id falls back to domain:index when raw id missing', () => {
  const out = normalizeQuality([{ summary: 'x' }, { summary: 'y' }], DATE)
  assert.equal(out[0].id, 'quality:0')
  assert.equal(out[1].id, 'quality:1')
})

test('null/undefined arrays normalize to empty', () => {
  assert.deepEqual(normalizeQuality(null, DATE), [])
  assert.deepEqual(normalizeReconciliation(undefined, DATE), [])
})

test('mergeAndSort sorts by occurredAt desc, ties broken by domain asc', () => {
  const out = mergeAndSort([
    [{ id: 'a', domain: 'quality', occurredAt: '2026-05-19T10:00:00' }],
    [{ id: 'b', domain: 'production', occurredAt: '2026-05-19T10:00:00' }],
    [{ id: 'c', domain: 'reconciliation', occurredAt: '2026-05-19T11:00:00' }]
  ])
  assert.deepEqual(out.map((e) => e.id), ['c', 'b', 'a'])
})
