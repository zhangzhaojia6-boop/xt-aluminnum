import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/master/Workshop.vue', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('Workshop master keeps the real workshop CRUD contract', () => {
  assert.match(source, /fetchWorkshopsPage/)
  assert.match(source, /createWorkshop/)
  assert.match(source, /updateWorkshop/)
  assert.match(source, /deleteWorkshop/)
  assert.match(masterApiSource, /api\.get\(`\/master\/\$\{resource\}`/)
  assert.match(masterApiSource, /api\.post\(`\/master\/\$\{resource\}`/)
  assert.match(masterApiSource, /api\.put\(`\/master\/\$\{resource\}\/\$\{id\}`/)
  assert.match(masterApiSource, /api\.delete\(`\/master\/\$\{resource\}\/\$\{id\}`/)
})

test('Workshop master preserves editable workshop fields', () => {
  for (const field of ['code', 'name', 'sort_order', 'is_active']) {
    assert.match(source, new RegExp(field))
  }
  for (const label of ['编码', '名称', '排序', '启用']) {
    assert.match(source, new RegExp(label))
  }
  assert.match(source, /normalizeWorkshopPayload\(form\)/)
  assert.match(source, /formRef\.value\.validate\(\)/)
})

test('Workshop master applies industrial blue master-data surface', () => {
  assert.match(source, /data-testid="admin-master-center"/)
  assert.match(source, /data-testid="workshop-master-nodes"/)
  assert.match(source, /data-testid="workshop-master-matrix"/)
  assert.match(source, /data-testid="workshop-master-mobile-list"/)
  assert.match(source, /MASTER DATA GRID/)
  assert.match(source, /--workshop-cyan:\s*#00f2ff/)
  assert.match(source, /workshopMasterSweep/)
  assert.match(source, /workshopMasterLed/)
})
