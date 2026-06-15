import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('mapping reconciliation page has a manage route and navigation entry', () => {
  const router = source('../src/router/index.js')
  const navigation = source('../src/config/manage-navigation.js')

  assert.match(router, /const MappingReconciliationPage = \(\) => import\('\.\.\/views\/manage\/mapping-reconciliation\/MappingReconciliationPage\.vue'\)/)
  assert.match(router, /path: 'mapping-reconciliation'/)
  assert.match(router, /name: 'manage-mapping-reconciliation'/)
  assert.match(router, /canonical: '\/manage\/mapping-reconciliation'/)
  assert.match(navigation, /输出skill对齐/)
  assert.match(navigation, /\/manage\/mapping-reconciliation/)
})

test('mapping reconciliation page uses real API functions and dry-run copy', () => {
  const apiPath = new URL('../src/api/mapping-reconciliation.js', import.meta.url)
  const pagePath = new URL('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue', import.meta.url)
  assert.equal(existsSync(apiPath), true)
  assert.equal(existsSync(pagePath), true)

  const api = source('../src/api/mapping-reconciliation.js')
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(api, /\/mapping-reconciliation\/sources/)
  assert.match(api, /\/mapping-reconciliation\/run/)
  assert.match(page, /data-testid="mapping-reconciliation-page"/)
  assert.match(page, /fetchMappingReconciliationSources/)
  assert.match(page, /runMappingReconciliation/)
  assert.match(page, /只读 dry-run/)
})

test('mapping reconciliation page can run selected file and business day dry-run', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /selectedReferenceFile/)
  assert.match(page, /businessDate/)
  assert.match(page, /reference_file:/)
  assert.match(page, /business_date:/)
  assert.match(page, /运行真实试算/)
  assert.doesNotMatch(page, /运行脱敏样例/)
  assert.doesNotMatch(page, /const dryRunPayload =/)
})

test('mapping reconciliation page compares scrap by default and renders metrics in Chinese', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /metric: 'scrap'/)
  assert.match(page, /reference_field: 'scrap_tons'/)
  assert.match(page, /system_field: 'scrap_tons'/)
  assert.match(page, /function metricLabel/)
  assert.match(page, /scrap: '废料'/)
  assert.match(page, /\{\{ metricLabel\(item\.metric\) \}\}/)
  assert.doesNotMatch(page, /<td>\{\{ item\.metric \}\}<\/td>/)
})

test('mapping reconciliation page compares input tons by default', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /metric: 'input'/)
  assert.match(page, /reference_field: 'input_tons'/)
  assert.match(page, /system_field: 'input_tons'/)
  assert.match(page, /input: '投入量'/)
})

test('mapping reconciliation page compares downtime and quality by default', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /metric: 'downtime'/)
  assert.match(page, /reference_field: 'downtime_minutes'/)
  assert.match(page, /system_field: 'downtime_minutes'/)
  assert.match(page, /metric: 'quality'/)
  assert.match(page, /reference_field: 'quality_issue_count'/)
  assert.match(page, /system_field: 'quality_issue_count'/)
  assert.match(page, /downtime: '停机'/)
  assert.match(page, /quality: '质量'/)
})

test('mapping reconciliation page compares yield rate per-ton material and cost by default', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /metric: 'yield'/)
  assert.match(page, /reference_field: 'yield_rate'/)
  assert.match(page, /system_field: 'yield_rate'/)
  assert.match(page, /metric: 'rolling_oil'/)
  assert.match(page, /reference_field: 'rolling_oil_per_ton'/)
  assert.match(page, /system_field: 'rolling_oil_per_ton'/)
  for (const field of ['liquefied_gas_per_ton', 'titanium_wire_per_ton', 'steel_strip_per_ton', 'd40_per_ton', 'filter_agent_per_ton', 'paint_per_ton']) {
    assert.match(page, new RegExp(`reference_field: '${field}'`))
    assert.match(page, new RegExp(`system_field: '${field}'`))
  }
  assert.match(page, /metric: 'cost'/)
  assert.match(page, /reference_field: 'cost_per_ton'/)
  assert.match(page, /system_field: 'cost_per_ton'/)
  assert.match(page, /metric: 'total_cost'/)
  assert.match(page, /reference_field: 'total_cost'/)
  assert.match(page, /system_field: 'total_cost'/)
  assert.match(page, /metric: 'throughput_cost'/)
  assert.match(page, /reference_field: 'throughput_cost_per_ton'/)
  assert.match(page, /system_field: 'throughput_cost_per_ton'/)
  assert.match(page, /yield: '成材率'/)
  assert.match(page, /rolling_oil: '轧制油吨耗'/)
  assert.match(page, /liquefied_gas: '液化气吨耗'/)
  assert.match(page, /titanium_wire: '钛丝吨耗'/)
  assert.match(page, /steel_strip: '钢带吨耗'/)
  assert.match(page, /d40: 'D40吨耗'/)
  assert.match(page, /filter_agent: '飞滤剂吨耗'/)
  assert.match(page, /paint: '油漆吨耗'/)
  assert.match(page, /cost: '吨成本'/)
  assert.match(page, /total_cost: '总成本'/)
  assert.match(page, /throughput_cost: '过站吨成本'/)
})

test('mapping reconciliation page renders backend difference summary', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /differenceSummary/)
  assert.match(page, /reasonBreakdown/)
  assert.match(page, /差异原因汇总/)
  assert.match(page, /result\.value\?\.difference_summary/)
  assert.match(page, /reason\.label/)
  assert.match(page, /reason\.count/)
})

test('mapping reconciliation page surfaces persisted run id from backend', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /runId/)
  assert.match(page, /运行编号/)
  assert.match(page, /result\.value\?\.run_id/)
})

test('mapping reconciliation page allows json reference files after backend parser support', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /'\.json'/)
})

test('mapping reconciliation page allows ndjson reference files after backend parser support', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /\['\.txt', '\.md', '\.log', '\.xlsx', '\.xls', '\.json', '\.ndjson'\]/)
})
