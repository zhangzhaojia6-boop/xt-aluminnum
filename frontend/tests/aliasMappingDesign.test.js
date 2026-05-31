import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/master/AliasMapping.vue', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('AliasMapping keeps the real alias CRUD contract', () => {
  assert.match(source, /fetchAliasMappings/)
  assert.match(source, /createAliasMapping/)
  assert.match(source, /updateAliasMapping/)
  assert.match(source, /deleteAliasMapping/)
  assert.match(masterApiSource, /api\.get\('\/master\/aliases'/)
  assert.match(masterApiSource, /api\.post\('\/master\/aliases'/)
  assert.match(masterApiSource, /api\.put\(`\/master\/aliases\/\$\{id\}`/)
  assert.match(masterApiSource, /api\.delete\(`\/master\/aliases\/\$\{id\}`/)
})

test('AliasMapping preserves all editable business fields', () => {
  for (const field of ['entity_type', 'canonical_code', 'alias_code', 'alias_name', 'source_type', 'is_active']) {
    assert.match(source, new RegExp(field))
  }
  for (const label of ['实体类型', '标准编码', '别名编码', '别名名称', '来源', '是否启用']) {
    assert.match(source, new RegExp(label))
  }
})

test('AliasMapping applies the industrial blue router surface', () => {
  assert.match(source, /data-testid="alias-router-page"/)
  assert.match(source, /data-testid="alias-filter-panel"/)
  assert.match(source, /data-testid="alias-matrix"/)
  assert.match(source, /data-testid="alias-mobile-list"/)
  assert.match(source, /ALIAS ROUTER/)
  assert.match(source, /--alias-cyan:\s*#00f2ff/)
  assert.match(source, /aliasRouterSweep/)
  assert.match(source, /aliasRouterLed/)
})
