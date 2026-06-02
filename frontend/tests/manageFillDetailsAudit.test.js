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
import {
  buildMissingReportRows,
  summarizeMissingReportRows,
} from '../src/utils/missingReportRows.js'

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
  assert.equal(items.find((item) => item.key === 'process-throughput')?.value, '90 吨')
  assert.equal(items.find((item) => item.key === 'contract-tonnage')?.value, '12.5 吨')
  assert.equal(items.find((item) => item.key === 'mes-sync')?.value, '同步恢复中')
})

test('audit ticker hides trailing zero decimals without losing non-zero decimals', () => {
  const items = buildAuditTickerItems({
    dailyOverview: {
      ...dailyOverview,
      plant_output: { daily_output: 81 },
      contracts: { daily_new: 12.5, unit: '吨' },
      workshop_output: [{ workshop: '退火一车间', daily_output: 40 }],
    },
  })

  assert.equal(items.find((item) => item.key === 'plant-output')?.value, '81 吨')
  assert.equal(items.find((item) => item.key === 'process-throughput')?.value, '40 吨')
  assert.equal(items.find((item) => item.key === 'contract-tonnage')?.value, '12.5 吨')
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
  assert.equal(cards.find((item) => item.key === 'energy')?.primaryValue, '1,200 度')
  assert.equal(cards.find((item) => item.key === 'energy')?.compareValue, '1,180 度')
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
        { key: 'contract_no', label: '合同号', value: 'HT-001', unit: '' },
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
  assert.match(rows[0].contentText, /合同号 HT-001/)
  assert.match(rows[1].contentText, /产量 9.5 吨/)
})

test('fill ledger search matches responsible person, machine and tracking card', () => {
  const rows = buildFillLedgerRows([
    { row_id: 'a', source_type: 'owner_daily', responsible_name: '张三', machine_name: '内勤岗' },
    { row_id: 'b', source_type: 'work_order_entry', responsible_name: '李四', machine_name: '1#退火炉', tracking_card_no: 'TX-001' },
    { row_id: 'c', source_type: 'mes_projection', responsible_name: '外部 MES', machine_name: 'MES 机列' },
  ])

  assert.deepEqual(filterFillLedgerRows(rows, { keyword: '张三' }).map((row) => row.rowId), ['a'])
  assert.deepEqual(filterFillLedgerRows(rows, { keyword: 'TX-001' }).map((row) => row.rowId), ['b'])
  assert.deepEqual(filterFillLedgerRows(rows, { sourceType: 'owner_daily' }).map((row) => row.rowId), ['a'])
  assert.deepEqual(rows.map((row) => row.rowId), ['a', 'b'])
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
    ['mes-unmatched', 3],
  ])

  const mesQueue = queues.find((item) => item.key === 'mes-unmatched')
  assert.deepEqual(mesQueue.items, ['未解析 3 条', '上游缺机列码 1 条'])
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
  assert.match(src, /fetchWorkshops/)
  assert.match(src, /data-testid="fill-details-workshop-filter"/)
  assert.match(src, /workshop_id:\s*selectedWorkshopId\.value/)
  assert.match(src, /data-testid="data-audit-ticker"/)
  assert.match(src, /data-testid="source-chain-panel"/)
  assert.match(src, /data-testid="issue-queue-panel"/)
  assert.doesNotMatch(src, /外部 MES/)
  assert.doesNotMatch(src, /value:\s*'mes_projection'/)
})

test('missing report rows are precise to machine shift and owner role', () => {
  const rows = buildMissingReportRows({
    workshops: [
      {
        workshop_id: 1,
        workshop_name: '铸轧三',
        machines: [
          {
            machine_id: 9,
            machine_name: '9#机',
            shifts: [
              { shift_id: 1, shift_name: '大夜', submission_status: 'not_started', status_text: '缺报', is_applicable: true },
              { shift_id: 2, shift_name: '长白班', submission_status: 'all_submitted', status_text: '已填', is_applicable: true },
            ],
          },
        ],
      },
    ],
    owner_daily_status: {
      items: [
        { user_id: 30, workshop_name: '成品库', role_label: '总电工', person_name: '王电工', status: 'not_started' },
      ],
    },
  })

  assert.deepEqual(rows.map((row) => [row.workshopName, row.machineName, row.shiftName, row.roleLabel, row.statusText]), [
    ['铸轧三', '9#机', '大夜', '主操', '缺报'],
    ['成品库', '每日一录', '每日一录', '总电工', '缺报'],
  ])
  assert.deepEqual(summarizeMissingReportRows(rows), {
    total: 2,
    workshopCount: 2,
    shiftCount: 2,
    roleCount: 2,
  })
})

test('TodayPage and WorkshopDashboardPage mount precise missing report panels', () => {
  const todaySrc = source('../src/views/manage/today/TodayPage.vue')
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(todaySrc, /MissingReportPanel/)
  assert.match(todaySrc, /compact/)
  assert.match(todaySrc, /fetchLiveAggregation/)
  assert.match(todaySrc, /buildMissingReportRows/)
  assert.match(dashboardSrc, /MissingReportPanel/)
  assert.match(dashboardSrc, /data-testid="workshop-dashboard-filter"/)
  assert.match(dashboardSrc, /fetchMesWorkshopProcessRecords\(scopedParams/)
  assert.match(dashboardSrc, /fetchMesMaterialRecords\(scopedParams/)
  assert.doesNotMatch(
    dashboardSrc,
    /unresolved_machine_count\s*\|\|\s*0\)\s*\+\s*Number\(mes\.upstream_machine_code_missing_count/,
  )
})

test('MissingReportPanel has compact density for yesterday report surface', () => {
  const src = source('../src/components/manage/MissingReportPanel.vue')

  assert.match(src, /compact/)
  assert.match(src, /xt-missing-report--compact/)
  assert.match(src, /max-height:\s*96px/)
})

test('WorkshopDashboardPage shows machine fill submit time', () => {
  const dashboardSrc = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')

  assert.match(dashboardSrc, /<th>填报时间<\/th>/)
  assert.match(dashboardSrc, /row\.submittedText/)
  assert.match(dashboardSrc, /colspan="7"/)
})
