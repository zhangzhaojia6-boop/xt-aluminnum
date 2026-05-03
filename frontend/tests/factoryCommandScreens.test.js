import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('factory command shell exposes production branches and freshness state', () => {
  const shell = source('../src/views/factory-command/FactoryCommandShell.vue')
  assert.match(shell, /工厂总览/)
  assert.match(shell, /生产流转/)
  assert.match(shell, /车间机列/)
  assert.match(shell, /卷级追踪/)
  assert.match(shell, /经营效益/)
  assert.match(shell, /库存去向/)
  assert.match(shell, /异常地图/)
  assert.match(shell, /freshnessLabel/)
})

test('factory overview and flow screens call factory command store', () => {
  const overview = source('../src/views/factory-command/FactoryOverview.vue')
  const shell = source('../src/views/factory-command/FactoryCommandShell.vue')
  const flow = source('../src/views/factory-command/ProductionFlowScreen.vue')
  assert.match(overview, /loadOverview/)
  assert.match(overview, /数据源/)
  assert.match(overview, /最后同步/)
  assert.match(overview, /问 AI/)
  assert.match(shell, /freshnessLabel\(freshness\?\.status, freshness\)/)
  assert.match(shell, /is-unconfigured/)
  assert.match(shell, /is-migration_missing/)
  assert.match(shell, /is-failed/)
  assert.doesNotMatch(shell, /last_error|lastError|error_message/)
  assert.match(flow, /loadCoils/)
  assert.match(flow, /前工序/)
  assert.match(flow, /当前工序/)
  assert.match(flow, /下工序/)
})

test('machine coil cost destination and exception screens expose required operating labels', () => {
  const machine = source('../src/views/factory-command/MachineLineScreen.vue')
  const coil = source('../src/views/factory-command/CoilTrace.vue')
  const cost = source('../src/views/factory-command/CostBenefitScreen.vue')
  const destination = source('../src/views/factory-command/DestinationScreen.vue')
  const exception = source('../src/views/factory-command/ExceptionMap.vue')

  assert.match(machine, /active_tons|activeTons/)
  assert.match(machine, /stalled_count|stalledCount/)
  assert.match(machine, /毛差估算/)
  assert.match(coil, /tracking_card_no|trackingCardNo/)
  assert.match(coil, /loadCoilFlow/)
  assert.match(cost, /经营估算/)
  assert.doesNotMatch(cost, /财务利润/)
  assert.match(destination, /成品库存/)
  assert.match(exception, /formatRuleLabel/)
  assert.doesNotMatch(exception, /\{\{\s*rule\.key\s*\}\}/)
})
