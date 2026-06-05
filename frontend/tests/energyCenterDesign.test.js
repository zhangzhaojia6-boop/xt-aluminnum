import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/energy/EnergyCenter.vue')
const apiPath = path.resolve('src/api/energy.js')
const src = fs.readFileSync(pagePath, 'utf8')
const apiSrc = fs.readFileSync(apiPath, 'utf8')

test('EnergyCenter keeps the real energy summary data path', () => {
  assert.match(src, /fetchEnergySummary/)
  assert.match(src, /business_date:\s*filters\.business_date/)
  assert.match(apiSrc, /api\.get\(['"]\/energy\/summary['"]/)
})

test('EnergyCenter keeps all management table fields visible', () => {
  for (const field of [
    'business_date',
    'workshop_code',
    'shift_code',
    'electricity_value',
    'gas_value',
    'water_value',
    'total_energy',
    'output_weight',
    'energy_per_ton'
  ]) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['业务日期', '车间', '班次', '电耗', '气耗', '水耗', '总能耗', '产量', '单吨能耗']) {
    assert.match(src, new RegExp(label))
  }
})

test('EnergyCenter keeps electricity and comprehensive energy separated', () => {
  assert.match(
    src,
    /<el-table-column prop="electricity_value" label="电耗"[\s\S]*?formatCell\(row\.electricity_value\)[\s\S]*?<\/el-table-column>/,
    'electricity column should render electricity_value only'
  )
  assert.match(
    src,
    /<el-table-column prop="total_energy" label="总能耗"[\s\S]*?formatCell\(row\.total_energy\)[\s\S]*?<\/el-table-column>/,
    'comprehensive energy column should render total_energy only'
  )
  assert.match(
    src,
    /\{ key: 'electricity', label: '电耗', value: formatStat\(sumBy\('electricity_value'\)\), unit: 'kWh'/,
    'electricity statistic should sum electricity_value'
  )
  assert.match(
    src,
    /\{ key: 'total', label: '总能耗', value: formatStat\(sumBy\('total_energy'\)\), unit: 'kgce'/,
    'comprehensive energy statistic should sum total_energy'
  )
  assert.doesNotMatch(src, /label:\s*'电耗'[\s\S]{0,120}sumBy\('total_energy'\)/)
  assert.doesNotMatch(src, /label:\s*'总能耗'[\s\S]{0,120}sumBy\('electricity_value'\)/)
})

test('EnergyCenter uses the industrial blue responsive surface', () => {
  assert.match(src, /data-testid="energy-center-page"/)
  assert.match(src, /data-testid="energy-center-stats"/)
  assert.match(src, /data-testid="energy-center-table"/)
  assert.match(src, /data-testid="energy-center-mobile-list"/)
  assert.match(src, /ENERGY COMMAND/)
  assert.match(src, /--energy-cyan:\s*#00f2ff/)
  assert.match(src, /energyCenterSweep/)
  assert.match(src, /energyCenterPulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('EnergyCenter does not add forbidden product wording', () => {
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
