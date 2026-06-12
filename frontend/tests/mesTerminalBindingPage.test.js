import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const pageSrc = readFileSync(new URL('../src/views/master/MesTerminalBinding.vue', import.meta.url), 'utf8')
const apiSrc = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')
const routerSrc = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const settingsSrc = readFileSync(new URL('../src/views/manage/admin/SystemSettingsPage.vue', import.meta.url), 'utf8')

test('MesTerminalBinding page keeps the real binding CRUD contract', () => {
  assert.match(pageSrc, /fetchMesTerminalBindings/)
  assert.match(pageSrc, /createMesTerminalBinding/)
  assert.match(pageSrc, /updateMesTerminalBinding/)
  assert.match(pageSrc, /deleteMesTerminalBinding/)
  assert.match(apiSrc, /api\.get\('\/master\/mes-terminal-bindings'/)
  assert.match(apiSrc, /api\.post\('\/master\/mes-terminal-bindings'/)
  assert.match(apiSrc, /api\.put\(`\/master\/mes-terminal-bindings\/\$\{id\}`/)
  assert.match(apiSrc, /api\.delete\(`\/master\/mes-terminal-bindings\/\$\{id\}`/)
})

test('MesTerminalBinding page preserves all binding fields', () => {
  for (const field of [
    'terminal_code',
    'terminal_name',
    'mes_device_name',
    'workshop_name',
    'process_name',
    'equipment_id',
    'confidence',
    'valid_from',
    'valid_to',
    'is_active'
  ]) {
    assert.match(pageSrc, new RegExp(field))
  }
})

test('MesTerminalBinding route and settings entry are wired', () => {
  assert.match(routerSrc, /MesTerminalBinding/)
  assert.match(routerSrc, /path: 'mes-terminal-bindings'/)
  assert.match(settingsSrc, /\/manage\/mes-terminal-bindings/)
  assert.match(settingsSrc, /终端绑定/)
})

test('MesTerminalBinding page has industrial blue surface and test ids', () => {
  assert.match(pageSrc, /data-testid="mes-terminal-binding-page"/)
  assert.match(pageSrc, /data-testid="mes-terminal-binding-table"/)
  assert.match(pageSrc, /terminal-binding__/)
  assert.match(pageSrc, /PC 终端/)
})
