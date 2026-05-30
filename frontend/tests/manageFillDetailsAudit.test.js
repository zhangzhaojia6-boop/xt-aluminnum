import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildAuditTickerItems,
  buildFillLedgerRows,
  buildIssueQueues,
  buildSourceChainCards,
  filterFillLedgerRows,
  MISSING_AUDIT_VALUE,
} from '../src/utils/manageFillDetailsAudit.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

const dailyOverview = {
  plant_output: {
    daily_output: 81.25,
    monthly_output: 1200,
    energy_per_ton: 456.7,
  },
  workshop_output: [
    { workshop: '退火一车间', daily_output: 40 },
    { workshop: '包装车间', daily_output: 50 },
    { workshop: '冷轧三车间', daily_output: 99 },
  ],
  contracts: {
    daily_new: 12.5,
    remaining: 88.2,
    unit: '吨',
  },
  energy: {
    total_electricity: 1200,
    owner_electricity: 1180,
    data_available: true,
  },
  yield_rates: {
    daily: 96.4,
    owner_daily: 95.1,
  },
}

test('audit ticker uses plant inbound output and ton contract values', () => {
  const items = buildAuditTickerItems({
    dailyOverview,
    liveAggregation: {
      mes_sync_status: { status: 'recovering', lag_seconds: 84 },
    },
  })

  assert.equal(items.find((item) => item.key === 'plant-output')?.value, '81.25 吨')
  assert.equal(items.find((item) => item.key === 'process-throughput')?.value, '90.00 吨')
  assert.equal(items.find((item) => item.key === 'contract-tonnage')?.value, '12.50 吨')
  assert.equal(items.find((item) => item.key === 'mes-sync')?.value, '同步恢复中')
})

test('audit ticker never renders fake zero when energy is unavailable', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      energy: {
        data_available: false,
        total_electricity: 0,
        owner_electricity: null,
      },
    },
  })

  assert.equal(items.find((item) => item.key === 'algorithm-energy')?.value, MISSING_AUDIT_VALUE)
  assert.equal(items.find((item) => item.key === 'owner-energy')?.value, MISSING_AUDIT_VALUE)
})

test('source chain cards keep algorithm values primary and filled values secondary', () => {
  const cards = buildSourceChainCards(dailyOverview)

  assert.deepEqual(
    cards.map((item) => [item.key, item.primaryLabel, item.compareLabel]),
    [
      ['output', '入库产量', '过站下机参考'],
      ['energy', '算法总用电', '电工填报'],
      ['yield', '算法成品率', '内勤填报'],
      ['contract', '当天接合同', '总余合同量'],
    ],
  )
  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, '1,200.00 度')
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '1,180.00 度')
})

test('fill ledger rows expose person, post, submit time and content', () => {
  const rows = buildFillLedgerRows([
    {
      row_id: 'entry-1',
      source_type: 'owner_daily',
      source_label: '每日一录',
      workshop_name: '成品库',
      machine_name: '内勤岗',
      responsible_name: '张三',
      responsible_username: 'zhangsan',
      submitted_at: '2026-05-30T08:12:00',
      status: 'submitted',
      metrics: [
        { key: 'total_electricity_kwh', label: '全厂用电', value: 1200, unit: 'kWh' },
      ],
    },
    {
      row_id: 'entry-2',
      source_type: 'work_order_entry',
      source_label: '机台填报',
      workshop_name: '退火一车间',
      machine_name: '1#退火炉',
      shift_name: '大夜',
      responsible_name: '李四',
      tracking_card_no: 'TX-001',
      output_weight: 9.5,
      updated_at: '2026-05-30T23:20:00',
      status: 'approved',
    },
  ])

  assert.equal(rows[0].machineName, '内勤岗')
  assert.equal(rows[0].shiftName, '每日一录')
  assert.equal(rows[0].responsibleText, '张三')
  assert.equal(rows[0].submittedText, '05-30 08:12')
  assert.match(rows[0].contentText, /全厂用电 1200kWh/)
  assert.match(rows[1].contentText, /产量 9.500 吨/)
})

test('fill ledger search matches responsible person, machine and tracking card', () => {
  const rows = buildFillLedgerRows([
    { row_id: 'a', source_type: 'owner_daily', responsible_name: '张三', machine_name: '内勤岗' },
    { row_id: 'b', source_type: 'work_order_entry', responsible_name: '李四', machine_name: '1#退火炉', tracking_card_no: 'TX-001' },
  ])

  assert.deepEqual(filterFillLedgerRows(rows, { keyword: '张三' }).map((row) => row.rowId), ['a'])
  assert.deepEqual(filterFillLedgerRows(rows, { keyword: 'TX-001' }).map((row) => row.rowId), ['b'])
  assert.deepEqual(filterFillLedgerRows(rows, { sourceType: 'owner_daily' }).map((row) => row.rowId), ['a'])
})

test('issue queues surface pending assignment, missing owner roles, energy gaps and MES gaps', () => {
  const queues = buildIssueQueues({
    dailyOverview: {
      energy: { data_available: false },
    },
    liveAggregation: {
      overall_progress: {
        pending_assignment: { entry_count: 2, missing_machine_count: 1 },
      },
      owner_daily_status: {
        items: [
          { status: 'not_started', role_label: '电工', person_name: '王五', workshop_name: '全厂专项' },
        ],
      },
      mes_machine_binding: {
        unresolved_machine_count: 3,
        upstream_machine_code_missing_count: 1,
      },
    },
  })

  assert.deepEqual(queues.map((item) => [item.key, item.count]), [
    ['pending-assignment', 2],
    ['missing-owner', 1],
    ['missing-energy', 1],
    ['mes-unmatched', 4],
  ])
})

test('issue queues keep pending assignment tone when backend uses fallback count field', () => {
  const queues = buildIssueQueues({
    liveAggregation: {
      overall_progress: {
        pending_assignment: { pending_assignment_entry_count: 2 },
      },
    },
  })

  const pending = queues.find((item) => item.key === 'pending-assignment')
  assert.equal(pending.count, 2)
  assert.equal(pending.tone, 'warning')
})

test('FillDetailsPage is wired to the three audit data sources', () => {
  const src = source('../src/views/manage/fill-details/FillDetailsPage.vue')

  assert.match(src, /fetchDailyProduction/)
  assert.match(src, /fetchLiveAggregation/)
  assert.match(src, /fetchLiveFillDetails/)
  assert.match(src, /data-testid="data-audit-ticker"/)
  assert.match(src, /data-testid="source-chain-panel"/)
  assert.match(src, /data-testid="issue-queue-panel"/)
})
