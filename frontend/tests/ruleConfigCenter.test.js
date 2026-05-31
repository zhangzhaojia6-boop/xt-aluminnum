import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const drawerSource = readFileSync(new URL('../src/config/manage-settings-drawer.js', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('rule config center is wired into admin management surface', () => {
  assert.match(routerSource, /RuleConfigCenter/)
  assert.match(routerSource, /path: 'admin\/rules'/)
  assert.match(drawerSource, /规则/)
  assert.match(drawerSource, /\/manage\/admin\/rules/)
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

test('rule config view keeps edit-save contract while adding industrial matrix surface', () => {
  const viewSource = readFileSync(new URL('../src/views/master/RuleConfigCenter.vue', import.meta.url), 'utf8')

  assert.match(viewSource, /class="page-stack rule-config-center"/)
  assert.match(viewSource, /RULE GOVERNANCE MATRIX/)
  assert.match(viewSource, /id="rule-config-title">规则配置/)
  assert.match(viewSource, /const ruleStats = computed/)
  assert.match(viewSource, /const dirtyCount = computed/)
  assert.match(viewSource, /function hasRuleChanged\(row\)/)
  assert.match(viewSource, /function ruleRowClassName/)
  assert.match(viewSource, /:row-class-name="ruleRowClassName"/)
  assert.match(viewSource, /:disabled="!hasRuleChanged\(row\)"/)
  assert.match(viewSource, /data-testid="rule-config-scope"/)
  assert.match(viewSource, /data-testid="rule-config-save"/)
  assert.match(viewSource, /data-testid="rule-config-mobile-save"/)
  assert.doesNotMatch(viewSource, /ReferencePageFrame/)
  assert.doesNotMatch(viewSource, /reference-page/)
})

test('rule config visual layer matches the industrial blue command style', () => {
  const viewSource = readFileSync(new URL('../src/views/master/RuleConfigCenter.vue', import.meta.url), 'utf8')

  assert.match(viewSource, /--rule-accent:\s*#00f2ff/)
  assert.match(viewSource, /rule-config-center__stat/)
  assert.match(viewSource, /RULE MATRIX/)
  assert.match(viewSource, /DEFAULT LAYER/)
  assert.match(viewSource, /@keyframes rulePanelIn/)
  assert.match(viewSource, /@keyframes ruleEnergyLine/)
  assert.match(viewSource, /prefers-reduced-motion/)
  assert.match(viewSource, /\.rule-table :deep\(\.el-table__row\.is-dirty td\.el-table__cell\)/)
  assert.match(viewSource, /\.rule-config-center__mobile-rules/)
  assert.match(viewSource, /\.rule-table\s*\{\s*display:\s*none;/)
})
