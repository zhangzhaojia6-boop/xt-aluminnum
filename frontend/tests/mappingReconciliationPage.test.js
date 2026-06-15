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

test('mapping reconciliation page renders backend difference summary', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /differenceSummary/)
  assert.match(page, /reasonBreakdown/)
  assert.match(page, /差异原因汇总/)
  assert.match(page, /result\.value\?\.difference_summary/)
  assert.match(page, /reason\.label/)
  assert.match(page, /reason\.count/)
})
