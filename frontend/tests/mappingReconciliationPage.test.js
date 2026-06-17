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
  assert.match(api, /\/mapping-reconciliation\/rules\/propose/)
  assert.match(api, /\/mapping-reconciliation\/rules\/apply-dry-run/)
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
  for (const field of [
    'liquefied_gas_per_ton',
    'titanium_wire_per_ton',
    'steel_strip_per_ton',
    'magnesium_per_ton',
    'manganese_per_ton',
    'iron_per_ton',
    'copper_per_ton',
    'hot_roll_emulsion_per_ton',
    'diatomite_per_ton',
    'white_earth_per_ton',
    'electricity_monthly',
    'electricity_target',
    'gas_monthly',
    'gas_target',
    'total_electricity_kwh',
    'new_plant_electricity_kwh',
    'park_electricity_kwh',
    'cast_roll_gas_m3',
    'smelting_gas_m3',
    'heating_furnace_gas_m3',
    'boiler_gas_m3',
    'total_gas_m3',
    'groundwater_ton',
    'tap_water_ton',
    'electricity_cost',
    'natural_gas_cost',
    'filter_cloth_daily',
    'high_temp_tape_daily',
    'regen_oil_out',
    'regen_oil_in',
    'hydraulic_oil_daily',
    'hydraulic_oil_monthly',
    'hydraulic_oil_target',
    'gear_oil_daily',
    'gear_oil_monthly',
    'gear_oil_target',
    'd40_per_ton',
    'steel_plate_per_ton',
    'steel_buckle_per_ton',
    'filter_agent_per_ton',
    'paint_per_ton',
    'ingot_block_count',
    'ingot_input_tons',
    'ingot_output_tons',
    'daily_contract_weight',
    'daily_hot_roll_contract_weight',
    'month_to_date_contract_weight',
    'remaining_contract_weight',
    'remaining_hot_roll_contract_weight',
    'remaining_contract_delta_weight',
    'billet_inventory_weight',
    'daily_input_weight',
    'month_to_date_input_weight'
  ]) {
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
  assert.match(page, /magnesium: '镁吨耗'/)
  assert.match(page, /manganese: '锰吨耗'/)
  assert.match(page, /iron: '铁吨耗'/)
  assert.match(page, /copper: '铜吨耗'/)
  assert.match(page, /hot_roll_emulsion: '热轧乳液吨耗'/)
  assert.match(page, /diatomite: '硅藻土吨耗'/)
  assert.match(page, /white_earth: '白土吨耗'/)
  assert.match(page, /electricity_monthly: '用电月累计'/)
  assert.match(page, /electricity_target: '用电指标'/)
  assert.match(page, /gas_monthly: '用气月累计'/)
  assert.match(page, /gas_target: '用气指标'/)
  assert.match(page, /total_electricity: '全厂用电'/)
  assert.match(page, /new_plant_electricity: '新厂用电'/)
  assert.match(page, /park_electricity: '园区用电'/)
  assert.match(page, /cast_roll_gas: '铸轧用气'/)
  assert.match(page, /smelting_gas: '熔炼炉用气'/)
  assert.match(page, /heating_furnace_gas: '加热炉用气'/)
  assert.match(page, /boiler_gas: '锅炉用气'/)
  assert.match(page, /total_gas: '天然气总量'/)
  assert.match(page, /groundwater: '地下水'/)
  assert.match(page, /tap_water: '自来水'/)
  assert.match(page, /electricity_cost: '电费'/)
  assert.match(page, /natural_gas_cost: '气费'/)
  assert.match(page, /filter_cloth: '滤布日耗'/)
  assert.match(page, /high_temp_tape: '高温胶带日耗'/)
  assert.match(page, /regen_oil_out: '再生油出库'/)
  assert.match(page, /regen_oil_in: '再生油入库'/)
  assert.match(page, /hydraulic_oil_daily: '液压油日耗'/)
  assert.match(page, /hydraulic_oil_monthly: '液压油月累计'/)
  assert.match(page, /hydraulic_oil_target: '液压油指标'/)
  assert.match(page, /gear_oil_daily: '齿轮油日耗'/)
  assert.match(page, /gear_oil_monthly: '齿轮油月累计'/)
  assert.match(page, /gear_oil_target: '齿轮油指标'/)
  assert.match(page, /d40: 'D40吨耗'/)
  assert.match(page, /steel_plate: '钢板吨耗'/)
  assert.match(page, /steel_buckle: '钢扣吨耗'/)
  assert.match(page, /filter_agent: '飞滤剂吨耗'/)
  assert.match(page, /paint: '油漆吨耗'/)
  assert.match(page, /ingot_block: '铸锭块数'/)
  assert.match(page, /ingot_input: '铸锭投料量'/)
  assert.match(page, /ingot_output: '铸锭下机量'/)
  assert.match(page, /daily_contract: '当日接合同'/)
  assert.match(page, /daily_hot_roll_contract: '当日热轧合同'/)
  assert.match(page, /month_to_date_contract: '月累计合同'/)
  assert.match(page, /remaining_contract: '余合同量'/)
  assert.match(page, /remaining_hot_roll_contract: '余热轧合同'/)
  assert.match(page, /remaining_contract_delta: '余合同较昨日'/)
  assert.match(page, /billet_inventory: '坯料总量'/)
  assert.match(page, /daily_input: '当日投料'/)
  assert.match(page, /month_to_date_input: '月累计投料'/)
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

test('mapping reconciliation page can dry-run proposed rules without applying them', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /applyMappingReconciliationRulesDryRun/)
  assert.match(page, /applyRuleDryRun/)
  assert.match(page, /rulePreview/)
  assert.match(page, /试算规则影响/)
  assert.match(page, /规则试算后匹配率/)
  assert.match(page, /applied: false/)
})

test('mapping reconciliation page renders backend field match summary', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /matchSummary/)
  assert.match(page, /fieldBreakdown/)
  assert.match(page, /字段匹配/)
  assert.match(page, /可比字段/)
  assert.match(page, /未匹配字段/)
  assert.match(page, /字段匹配率/)
  assert.match(page, /result\.value\?\.match_summary/)
  assert.match(page, /item\.match_rate/)
})

test('mapping reconciliation page surfaces parseable coverage and image pending files', () => {
  const page = source('../src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue')

  assert.match(page, /fileSummary/)
  assert.match(page, /可解析覆盖率/)
  assert.match(page, /图片待解析/)
  assert.match(page, /parseable_coverage_rate/)
  assert.match(page, /image_pending_files/)
  assert.match(page, /image_pending_ocr/)
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
