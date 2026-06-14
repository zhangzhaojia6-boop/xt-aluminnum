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
