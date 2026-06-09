import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const pagePath = new URL('../src/views/energy/EnergyCenter.vue', import.meta.url)
const apiPath = new URL('../src/api/energy.js', import.meta.url)
const surfacePath = new URL('../src/utils/stitchManageSurface.js', import.meta.url)
const src = fs.readFileSync(pagePath, 'utf8')
const apiSrc = fs.readFileSync(apiPath, 'utf8')
const surfaceSrc = fs.readFileSync(surfacePath, 'utf8')

test('EnergyCenter keeps the real energy summary data path', () => {
  assert.match(src, /fetchEnergySummary/)
  assert.match(src, /business_date:\s*filters\.business_date/)
  assert.match(apiSrc, /api\.get\(['"]\/energy\/summary['"]/)
  assert.match(apiSrc, /skipAuthLogout:\s*true/)
  assert.match(apiSrc, /skipErrorToast:\s*true/)
})

test('EnergyCenter consumes the Stitch energy surface without changing the API contract', () => {
  assert.match(src, /buildEnergyStitchSurface/)
  assert.match(src, /stitchSurface\s*=\s*computed\(\(\)\s*=>\s*buildEnergyStitchSurface/)
  assert.match(src, /kpiItems:\s*rawEnergyStats\.value/)
  assert.match(src, /detailRows:\s*rows\.value/)
  assert.match(src, /statusBar\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.statusBar/)
  assert.match(src, /data-testid="energy-center-status-bar"/)
  assert.match(src, /statusBar\.syncStatus/)
  assert.match(src, /statusBar\.rowCount/)
  assert.match(src, /data-testid="stitch-bottom-status"/)
  assert.match(src, /bottomStatusItems\s*=\s*computed\(\(\)\s*=>\s*stitchSurface\.value\.bottomStatus/)
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
  assert.match(src, /energy-center__flow-card--endpoint/)
  assert.match(src, /energy-center__flow-card--result/)
  assert.match(src, /energy-center__flow-card--critical/)
  assert.match(src, /energy-center__flow-icon--meter/)
  assert.match(src, /energy-center__flow-icon--flame/)
  assert.match(src, /energy-center__flow-icon--converter/)
  assert.doesNotMatch(src, /energyCenterSweep/)
  assert.doesNotMatch(src, /energyCenterPulse/)
  assert.doesNotMatch(src, /animation:\s*[^;]*infinite/)
  assert.doesNotMatch(src, /backdrop-filter|filter:\s*blur/i)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('EnergyCenter matches the target dashboard granularity instead of plain cards', () => {
  assert.match(src, /label:\s*'产量'[\s\S]{0,140}sumBy\('output_weight'\)/)
  assert.match(src, /label:\s*'单吨峰值'[\s\S]{0,140}maxBy\('energy_per_ton'\)/)
  assert.match(src, /updatedAt\.value/)
  assert.match(src, /statusBar\.updatedAt/)
  assert.match(src, /页面刷新/)
  assert.match(src, /ENERGY WATCH/)
  assert.match(src, /能耗关注/)
  assert.match(surfaceSrc, /gas-top/)
  assert.match(surfaceSrc, /water-top/)
  assert.match(surfaceSrc, /output-top/)
  assert.match(src, /grid-template-columns:\s*repeat\(6,\s*minmax\(0,\s*1fr\)\)/)
})

test('EnergyCenter reloads when the selected business date changes and explains permission failures', () => {
  assert.match(src, /import\s+\{\s*computed,\s*onMounted,\s*reactive,\s*ref\s*\}\s+from\s+'vue'/)
  assert.match(src, /import DateSwitcher/)
  assert.match(src, /<DateSwitcher/)
  assert.match(src, /@step="handleBusinessDateStep"/)
  assert.match(src, /@pick="handleBusinessDatePick"/)
  assert.match(src, /@refresh="load"/)
  assert.match(src, /function setBusinessDate\(value\)/)
  assert.match(src, /function handleBusinessDateStep\(deltaDays\)/)
  assert.match(src, /function handleBusinessDatePick\(value\)/)
  assert.match(src, /void\s+load\(\)/)
  assert.match(src, /resolveEnergyErrorText/)
  assert.match(src, /无权限查看能耗数据/)
  assert.match(src, /请先登录后查看能耗数据/)
})

test('EnergyCenter does not add forbidden product wording', () => {
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
