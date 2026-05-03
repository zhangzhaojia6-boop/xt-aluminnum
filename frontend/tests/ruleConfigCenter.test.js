import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSource = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('rule config center is wired into admin management surface', () => {
  assert.match(routerSource, /RuleConfigCenter/)
  assert.match(routerSource, /path: 'admin\/rules'/)
  assert.match(navSource, /规则配置/)
  assert.match(navSource, /\/manage\/admin\/rules/)
})

test('rule config api exposes scoped list and upsert calls', () => {
  assert.match(masterApiSource, /fetchRuleConfigs/)
  assert.match(masterApiSource, /upsertRuleConfig/)
  assert.match(masterApiSource, /updateRuleConfig/)
})

test('rule config view uses workshop scoped thresholds without helper copy', () => {
  const viewSource = readFileSync(new URL('../src/views/master/RuleConfigCenter.vue', import.meta.url), 'utf8')

  assert.match(viewSource, /data-testid="rule-config-page"/)
  assert.match(viewSource, /MAX_SINGLE_SHIFT_WEIGHT/)
  assert.match(viewSource, /scope_key/)
  assert.doesNotMatch(viewSource, /helperText|description|tooltip|explanation|rationale/)
})
