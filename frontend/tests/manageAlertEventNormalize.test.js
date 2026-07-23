import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildAlertWorkQueues,
  groupAlertEvents,
  normalizeDailyFactAlerts,
  normalizeFactoryDirector,
  normalizeMesFillGaps,
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
  assert.equal(out[0].detailRoute, '/manage/alerts?surface=anomaly')
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

test('normalizeFactoryDirector composes summary from workshop+shift+exception_type when missing', () => {
  const payload = {
    exception_lane: {
      recent_items: [
        { report_id: 'p1', workshop_name: '一车间', shift_name: '早班', exception_type: 'output_anomaly', note: '产量为 0' }
      ]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.match(out[0].summary, /一车间 早班/)
  assert.match(out[0].detail, /产量为 0/)
  assert.equal(out[0].id, 'production:p1')
})

test('normalizeFactoryDirector returned_items use returned_reason as summary', () => {
  const payload = {
    exception_lane: {
      returned_items: [
        { report_id: 'r1', workshop_name: '二车间', shift_name: '大夜', returned_reason: '数据缺失需补录' }
      ]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out[0].summary, '二车间 大夜班：数据缺失需补录')
  assert.equal(out[0].domain, 'reporting')
})

test('normalizeQuality uses issue_desc when summary missing (real backend shape)', () => {
  const items = [
    { id: 6, issue_desc: '当日未导入能耗数据', issue_type: 'completeness', dimension_key: 'energy', created_at: '2026-05-19T11:00:00' }
  ]
  const out = normalizeQuality(items, DATE)
  assert.equal(out[0].summary, '当日未导入能耗数据')
  assert.match(out[0].detail, /completeness/)
  assert.match(out[0].detail, /energy/)
  assert.equal(out[0].id, 'quality:6')
  assert.equal(out[0].occurredAt, '2026-05-19T11:00:00')
})

test('normalizeReconciliation composes summary from source_a/source_b values', () => {
  const items = [
    {
      id: 9,
      reconciliation_type: 'cross_source',
      dimension_key: 'production_kg',
      source_a_value: 12345,
      source_b_value: 12100,
      created_at: '2026-05-19T09:50:00'
    }
  ]
  const out = normalizeReconciliation(items, DATE)
  assert.match(out[0].summary, /production_kg/)
  assert.match(out[0].summary, /12345/)
  assert.match(out[0].summary, /12100/)
  assert.match(out[0].detail, /production_kg/)
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
  assert.equal(out[0].detailRoute, '/manage/alerts?surface=quality')
})

test('normalizeReconciliation maps to reconciliation domain', () => {
  const items = [{ id: 'r1', summary: '过磅差异', occurred_at: '2026-05-19T09:50:00' }]
  const out = normalizeReconciliation(items, DATE)
  assert.equal(out[0].domain, 'reconciliation')
  assert.equal(out[0].detailRoute, '/manage/alerts?surface=reconciliation')
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

test('groupAlertEvents folds repeated fact evidence into one auditable action case', () => {
  const raw = normalizeDailyFactAlerts({
    fact_conflicts: [
      {
        id: 'yield-1',
        field: 'daily_yield_rate',
        status: 'mismatch',
        trace_id: 'trace-yield-1',
        target_date: DATE,
      },
      {
        id: 'yield-2',
        field: 'daily_yield_rate',
        status: 'mismatch',
        trace_id: 'trace-yield-2',
        target_date: DATE,
      },
    ],
  }, DATE)

  const cases = groupAlertEvents(raw)

  assert.equal(raw.length, 2)
  assert.equal(cases.length, 1)
  assert.equal(cases[0].rawCount, 2)
  assert.equal(cases[0].rawOpenCount, 2)
  assert.deepEqual(cases[0].sourceEventIds, ['fact-conflict:yield-1', 'fact-conflict:yield-2'])
  assert.deepEqual(cases[0].traceIds, ['trace-yield-1', 'trace-yield-2'])
  assert.equal(cases[0].sourceEvents.length, 2)
  assert.equal(cases[0].status, 'open')
  assert.match(cases[0].detail, /2 条原始记录/)
  assert.match(cases[0].detail, /2 个追踪编号/)
})

test('groupAlertEvents groups MES batch rows only when the action identity matches', () => {
  const raw = normalizeMesFillGaps({
    items: [
      {
        status: 'mes_batch_unmapped',
        workshop_id: 9,
        workshop_name: '精整车间',
        mes_machine_name: 'PC',
        shift_name: '长白班',
        process_name: '包装',
        batch_no: 'B-001',
      },
      {
        status: 'mes_batch_unmapped',
        workshop_id: 9,
        workshop_name: '精整车间',
        mes_machine_name: 'PC',
        shift_name: '长白班',
        process_name: '包装',
        batch_no: 'B-002',
      },
      {
        status: 'mes_batch_unmapped',
        workshop_id: 9,
        workshop_name: '精整车间',
        mes_machine_name: 'PC',
        shift_name: '大夜班',
        process_name: '包装',
        batch_no: 'B-003',
      },
    ],
  }, DATE)

  const cases = groupAlertEvents(raw)

  assert.equal(cases.length, 2)
  assert.equal(cases.find((item) => item.rawCount === 2)?.sourceEvents.length, 2)
  assert.equal(cases.find((item) => item.rawCount === 1)?.sourceEvents[0].id, 'mes-fill-gap:B-003')
})

test('groupAlertEvents never merges events without an explicit source-derived group key', () => {
  const cases = groupAlertEvents([
    { id: 'a', domain: 'production', summary: '同一句摘要', status: 'open' },
    { id: 'a', domain: 'production', summary: '来源编号也重复', status: 'open' },
    { domain: 'production', summary: '无来源编号', status: 'open' },
    { domain: 'production', summary: '无来源编号', status: 'open' },
  ])

  assert.equal(cases.length, 4)
  assert.deepEqual(cases.map((item) => item.rawCount), [1, 1, 1, 1])
})

test('daily agent failures stay separate unless the source provides an explicit action identity', () => {
  const raw = normalizeDailyFactAlerts({
    hermes_failures: [
      { id: 'run-1', status: 'failed', target_date: DATE },
      { id: 'run-2', status: 'failed', target_date: DATE },
    ],
    dingtalk_inbound_failures: [
      { id: 'inbound-1', status: 'failed', target_date: DATE },
      { id: 'inbound-2', status: 'failed', target_date: DATE },
    ],
  }, DATE)

  assert.equal(groupAlertEvents(raw).length, 4)
})

test('buildAlertWorkQueues groups events into actionable management queues', () => {
  const queues = buildAlertWorkQueues([
    { id: 'a', domain: 'reporting', summary: '热轧 长白班 缺报', status: 'open' },
    { id: 'b', domain: 'production', summary: '能耗暂无可信数据', status: 'open' },
    { id: 'c', domain: 'production', summary: 'MES 未匹配机列 18 条', status: 'open' },
    { id: 'd', domain: 'quality', summary: '抽检异常', status: 'open' },
    { id: 'e', domain: 'reconciliation', summary: '算法与填报差异', status: 'resolved' },
  ])

  assert.deepEqual(queues.map((queue) => [queue.key, queue.count]), [
    ['reporting', 1],
    ['energy', 1],
    ['mes', 1],
    ['quality', 1],
    ['reconciliation', 1],
    ['production', 0],
  ])
  assert.equal(queues.find((queue) => queue.key === 'reconciliation')?.openCount, 0)
})

test('buildAlertWorkQueues reports action cases and raw evidence counts separately', () => {
  const queues = buildAlertWorkQueues([
    {
      id: 'mes-1',
      groupKey: 'mes:unmapped:9:PC:day:pack',
      domain: 'mes',
      summary: 'MES 批号未映射',
      status: 'open',
      traceId: 'trace-mes-1',
    },
    {
      id: 'mes-2',
      groupKey: 'mes:unmapped:9:PC:day:pack',
      domain: 'mes',
      summary: 'MES 批号未映射',
      status: 'open',
      traceId: 'trace-mes-2',
    },
  ])

  const mesQueue = queues.find((queue) => queue.key === 'mes')
  assert.equal(mesQueue.count, 1)
  assert.equal(mesQueue.rawCount, 2)
  assert.equal(mesQueue.openCount, 1)
  assert.equal(mesQueue.openRawCount, 2)
  assert.equal(mesQueue.items[0].rawCount, 2)
  assert.equal(mesQueue.items[0].traceCount, 2)
})

test('buildAlertWorkQueues keeps known quality and reconciliation domains before keyword matching', () => {
  const queues = buildAlertWorkQueues([
    { id: 'q-energy', domain: 'quality', summary: '当日未导入能耗数据', status: 'open' },
    { id: 'r-mes', domain: 'reconciliation', summary: '生产与 MES 核对差异', status: 'open' },
    { id: 'p-energy', domain: 'production', summary: '总电耗暂无可信数据', status: 'open' },
    { id: 'p-mes', domain: 'production', summary: 'MES 未匹配机列 18 条', status: 'open' },
  ])

  assert.equal(queues.find((queue) => queue.key === 'quality')?.count, 1)
  assert.equal(queues.find((queue) => queue.key === 'reconciliation')?.count, 1)
  assert.equal(queues.find((queue) => queue.key === 'energy')?.count, 1)
  assert.equal(queues.find((queue) => queue.key === 'mes')?.count, 1)
})

test('buildAlertWorkQueues excludes capability fallbacks from every business queue', () => {
  const queues = buildAlertWorkQueues([
    {
      id: 'fact-closure-capability:missing',
      domain: 'reporting',
      summary: '当日事实闭包不可用',
      status: null,
      isFallback: true,
    },
  ])

  assert.equal(queues.reduce((sum, queue) => sum + queue.count, 0), 0)
  assert.equal(queues.reduce((sum, queue) => sum + queue.openCount, 0), 0)
  assert.deepEqual(queues.flatMap((queue) => queue.items), [])
})
