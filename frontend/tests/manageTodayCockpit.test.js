import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFilerRoster,
  rosterStats,
  statusTone,
  statusLabel,
  getMachinesFor
} from '../src/components/manage/_filerRoster.js'
import {
  shapeTrendSeries,
  trendStats
} from '../src/components/manage/_outputTrend.js'

const USERS = [
  { id: 1, role: 'machine_operator', workshop_id: 1, name: '铸锭车间 1# 主操', is_active: true },
  { id: 2, role: 'machine_operator', workshop_id: 1, name: '铸锭车间 2# 主操', is_active: true },
  { id: 3, role: 'machine_operator', workshop_id: 2, name: '铸二车间 1# 主操', is_active: true },
  { id: 4, role: 'admin', workshop_id: 1, name: 'should be excluded' }
]

test('buildFilerRoster joins workshop status with operators by workshop_id', () => {
  const status = [
    { workshop_id: 1, workshop_name: '铸锭车间', source_label: '主操直录', report_status: 'submitted', output_weight: 120 },
    { workshop_id: 2, workshop_name: '铸二车间', source_label: '主操直录', report_status: 'unreported' }
  ]
  const out = buildFilerRoster(status, USERS)
  assert.equal(out.length, 2)
  assert.deepEqual(out.map((row) => row.workshopName), ['铸锭', '铸二'])
  assert.deepEqual(out[0].operators.map((o) => o.name), ['铸锭车间 1# 主操', '铸锭车间 2# 主操'])
  assert.equal(out[0].operatorCount, 2)
  assert.equal(out[0].reportStatus, 'submitted')
  assert.equal(out[1].operators[0].name, '铸二车间 1# 主操')
})

test('buildFilerRoster excludes non-operators and inactive users', () => {
  const status = [{ workshop_id: 1, workshop_name: '铸锭车间', report_status: 'unreported' }]
  const out = buildFilerRoster(status, [
    ...USERS,
    { id: 99, role: 'machine_operator', workshop_id: 1, name: 'inactive', is_active: false }
  ])
  assert.equal(out[0].operators.length, 2)
  assert.ok(!out[0].operators.find((o) => o.name === 'inactive'))
})

test('buildFilerRoster ignores workshops outside the active twelve-workshop surface', () => {
  const status = [{ workshop_id: 999, workshop_name: '新车间', report_status: 'unreported' }]
  const out = buildFilerRoster(status, USERS)
  assert.deepEqual(out, [])
})

test('rosterStats counts by tone', () => {
  const roster = [
    { reportStatus: 'submitted' },
    { reportStatus: 'reported' },
    { reportStatus: 'late' },
    { reportStatus: 'unreported' },
    { reportStatus: 'unreported' },
    { reportStatus: 'returned' }
  ]
  const s = rosterStats(roster)
  assert.equal(s.total, 6)
  assert.equal(s.reported, 2)
  assert.equal(s.abnormal, 1)
  assert.equal(s.unreported, 3)
})

test('statusTone/statusLabel cover known statuses + fallback', () => {
  assert.equal(statusTone('submitted'), 'success')
  assert.equal(statusTone('returned'), 'danger')
  assert.equal(statusTone('late'), 'warning')
  assert.equal(statusTone('unknown'), 'muted')
  assert.equal(statusLabel('submitted'), '已报')
  assert.equal(statusLabel('returned'), '退回')
  assert.equal(statusLabel(''), '未报')
})

test('shapeTrendSeries tails to N days, maps date label, converts kg → t', () => {
  const raw = Array.from({ length: 30 }, (_, i) => ({
    date: `2026-05-${String(i + 1).padStart(2, '0')}`,
    output_weight: (i + 1) * 1000
  }))
  const out = shapeTrendSeries(raw, 14)
  assert.equal(out.length, 14)
  assert.equal(out[0].label, '05-17')
  assert.equal(out[13].label, '05-30')
  assert.equal(out[13].output, 30)
})

test('trendStats computes max/avg/last over valid points', () => {
  const series = [
    { output: 10 }, { output: 20 }, { output: 30 }
  ]
  const s = trendStats(series)
  assert.equal(s.max, 30)
  assert.equal(s.avg, 20)
  assert.equal(s.last, 30)
})

test('trendStats safe on empty', () => {
  const s = trendStats([])
  assert.equal(s.max, 0)
  assert.equal(s.avg, 0)
  assert.equal(s.last, 0)
})

test('getMachinesFor returns inventory by workshop name', () => {
  const m1 = getMachinesFor('铸锭车间')
  assert.equal(m1.length, 4)
  assert.equal(m1[0].id, '1#')
  assert.equal(m1[0].online, true)

  const zr2 = getMachinesFor('铸二车间')
  assert.equal(zr2.length, 6)
  assert.equal(zr2.find((m) => m.id === '5#').online, false)

  const rz = getMachinesFor('热轧车间')
  assert.ok(rz.find((m) => m.id === '热轧机' && m.online))
  assert.equal(getMachinesFor('冷轧三车间').length, 0)
  assert.equal(getMachinesFor('不存在车间').length, 0)
})

test('buildFilerRoster attaches machines + onlineCount when workshop_name matches inventory', () => {
  const status = [
    { workshop_id: 2, workshop_name: '铸二车间', report_status: 'submitted' },
    { workshop_id: 999, workshop_name: '陌生车间', report_status: 'unreported' }
  ]
  const out = buildFilerRoster(status, [])
  assert.equal(out[0].machineCount, 6)
  assert.equal(out[0].onlineCount, 5)
  assert.equal(out[0].machines.find((m) => m.id === '5#').online, false)
  assert.equal(out.length, 1)
})
