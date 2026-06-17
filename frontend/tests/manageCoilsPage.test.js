import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const pageSrc = readFileSync(new URL('../src/views/manage/coils/CoilTracePage.vue', import.meta.url), 'utf8')
const apiSrc = readFileSync(new URL('../src/api/factory-command.js', import.meta.url), 'utf8')
const routerSrc = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSrc = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')
const navigationSrc = readFileSync(new URL('../src/config/navigation.js', import.meta.url), 'utf8')
const shellSrc = readFileSync(new URL('../src/layout/ManageShell.vue', import.meta.url), 'utf8')

test('manage coils page uses the real factory command coil APIs', () => {
  assert.match(pageSrc, /fetchFactoryCommandCoils/)
  assert.match(pageSrc, /fetchFactoryCommandCoilFlow/)
  assert.match(apiSrc, /api\.get\('\/factory-command\/coils'/)
  assert.match(apiSrc, /api\.get\(`\/factory-command\/coils\/\$\{encodeURIComponent\(coilKey\)\}\/flow`/)
})

test('manage coils route is wired as a review management page', () => {
  assert.match(routerSrc, /CoilTracePage/)
  assert.match(routerSrc, /path: 'coils'/)
  assert.match(routerSrc, /name: 'manage-coils'/)
  assert.match(routerSrc, /canonical: '\/manage\/coils'/)
})

test('manage coils is visible in navigation and command metadata', () => {
  assert.match(navSrc, /\/manage\/coils/)
  assert.match(navSrc, /卷级线索/)
  assert.match(navigationSrc, /routeName: 'manage-coils'/)
  assert.match(navigationSrc, /'manage-coils'/)
  assert.match(shellSrc, /\/manage\/coils/)
})

test('manage coils page exposes searchable coil trace surface', () => {
  assert.match(pageSrc, /data-testid="manage-coils"/)
  assert.match(pageSrc, /data-testid="manage-coils-table"/)
  assert.match(pageSrc, /data-testid="manage-coils-flow"/)
  assert.match(pageSrc, /data-testid="manage-coils-filter-summary"/)
  assert.match(pageSrc, /placeholder="搜索随行卡、批号、合金、机列"/)
  assert.match(pageSrc, /placeholder="筛选客户"/)
  assert.match(pageSrc, /placeholder="合金\/规格"/)
  assert.match(pageSrc, /placeholder="当前工艺"/)
  assert.match(pageSrc, /aria-label="筛选机列状态"/)
  assert.match(pageSrc, /待绑定机列/)
  assert.match(pageSrc, /已匹配机列/)
  assert.match(pageSrc, /MES 主数据/)
  assert.match(pageSrc, /人工补录对照/)
  assert.match(pageSrc, /待绑定/)
})

test('manage coils page filters loaded coils locally without changing the API contract', () => {
  assert.match(pageSrc, /rawCoils/)
  assert.match(pageSrc, /visibleCoils/)
  assert.match(pageSrc, /matchText/)
  assert.match(pageSrc, /machineStateMatches/)
  assert.match(pageSrc, /hasBoundMachine/)
  assert.match(pageSrc, /isUnknownMachineLabel/)
  assert.doesNotMatch(apiSrc, /customer_alias/)
  assert.doesNotMatch(apiSrc, /machine_state/)
})

test('manage coils page shows MES weight and automatic scrap clues separately', () => {
  assert.match(pageSrc, /mes_input_weight_tons/)
  assert.match(pageSrc, /mes_output_weight_tons/)
  assert.match(pageSrc, /auto_scrap_weight_tons/)
  assert.match(pageSrc, /auto_scrap_rate/)
  assert.match(pageSrc, /scrap_status/)
  assert.match(pageSrc, /MES 上机/)
  assert.match(pageSrc, /MES 下机/)
  assert.match(pageSrc, /自动废料/)
  assert.match(pageSrc, /废料率/)
  assert.match(pageSrc, /异常审核/)
})

test('manage coils page displays MES identity, spec, status and weight clues', () => {
  assert.match(pageSrc, /客户\/合同/)
  assert.match(pageSrc, /合金规格/)
  assert.match(pageSrc, /MES 卷重/)
  assert.match(pageSrc, /customerContractText/)
  assert.match(pageSrc, /weightTraceText/)
  assert.match(pageSrc, /lifecycleText/)
  assert.match(pageSrc, /statusText/)
  assert.match(pageSrc, /contract_no/)
  assert.match(pageSrc, /material_weight/)
  assert.match(pageSrc, /last_seen_from_mes_at/)
})
