import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('factory command shell exposes production branches and freshness state', () => {
  const shell = source('../src/views/factory-command/FactoryCommandShell.vue')
  assert.match(shell, /'overview'.*'总览'/)
  assert.match(shell, /'production'.*'生产'/)
  assert.match(shell, /'destinations'.*'库存去向'/)
  assert.match(shell, /'exceptions'.*'异常'/)
  assert.match(shell, /\/manage\/today/)
  assert.match(shell, /\/manage\/production/)
  assert.match(shell, /\/manage\/alerts\?surface=anomaly/)
  assert.match(shell, /freshnessLabel/)
  assert.match(shell, /font-family: var\(--xt-font-body\)/)
  assert.doesNotMatch(shell, /'Inter'/)
  assert.doesNotMatch(shell, /transition:\s*all/)
})

test('retired factory command screens are absent while destination remains reachable', () => {
  const destination = source('../src/views/factory-command/DestinationScreen.vue')
  const router = source('../src/router/index.js')

  for (const path of [
    '../src/views/factory-command/FactoryOverview.vue',
    '../src/views/factory-command/ProductionFlowScreen.vue',
    '../src/views/factory-command/MachineLineScreen.vue',
    '../src/views/factory-command/CoilTrace.vue',
    '../src/views/factory-command/CostBenefitScreen.vue',
    '../src/views/factory-command/ExceptionMap.vue'
  ]) {
    assert.equal(existsSync(new URL(path, import.meta.url)), false, `${path} should be deleted`)
  }

  assert.match(destination, /成品库存/)
  assert.match(router, /path: 'factory\/destinations'[\s\S]*component: DestinationScreen/)
  assert.doesNotMatch(router, /factory\/flow|factory\/machine-lines|factory\/coils|factory\/cost/)
})

test('factory cost routes are removed from manage children', () => {
  const router = source('../src/router/index.js')

  assert.doesNotMatch(router, /CostAccountingCenter/)
  assert.doesNotMatch(router, /path: 'factory\/cost'/)
  assert.doesNotMatch(router, /path: 'factory\/cost\/accounting'/)
})
