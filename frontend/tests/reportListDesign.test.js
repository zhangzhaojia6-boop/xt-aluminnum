import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/reports/ReportList.vue')
const apiPath = path.resolve('src/api/reports.js')
const src = fs.readFileSync(pagePath, 'utf8')
const apiSrc = fs.readFileSync(apiPath, 'utf8')

test('ReportList keeps the real report archive data path', () => {
  assert.match(src, /fetchReports/)
  assert.match(src, /filters\.start_date/)
  assert.match(src, /filters\.end_date/)
  assert.match(src, /delete params\.report_type/)
  assert.match(src, /delete params\.status/)
  assert.match(src, /ElMessage\.error\(['"]日报加载失败['"]\)/)
  assert.match(apiSrc, /api\.get\(['"]\/reports['"]/)
})

test('ReportList keeps every archive table field visible', () => {
  for (const field of [
    'id',
    'report_date',
    'report_type',
    'status',
    'generated_scope',
    'output_mode',
    'is_final_version',
    'published_at',
    'report_data'
  ]) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['编号', '报告日期', '报告类型', '当前状态', '生成范围', '输出方式', '归档版本', '最新输出时间', '关键摘要']) {
    assert.match(src, new RegExp(label))
  }
})

test('ReportList keeps display helpers and summary semantics', () => {
  assert.match(src, /formatReportTypeLabel/)
  assert.match(src, /formatReportScopeLabel/)
  assert.match(src, /formatOutputModeLabel/)
  assert.match(src, /formatReportStatus/)
  assert.match(src, /toLowerCase\(\)\s*===\s*['"]reviewed['"]/)
  assert.match(src, /return ['"]已校验['"]/)
  assert.match(src, /buildSummaryLine/)
  assert.match(src, /total_output_weight/)
  assert.match(src, /reporting_rate/)
  assert.match(src, /anomaly_summary/)
  assert.match(src, /legacy_profile/)
})

test('ReportList uses the industrial blue responsive delivery surface', () => {
  assert.match(src, /data-testid="report-delivery-page"/)
  assert.match(src, /data-testid="report-delivery-filters"/)
  assert.match(src, /data-testid="report-delivery-stats"/)
  assert.match(src, /data-testid="report-delivery-table"/)
  assert.match(src, /data-testid="report-delivery-mobile-list"/)
  assert.match(src, /日报交付/)
  assert.match(src, /交付清单/)
  assert.match(src, /--report-cyan:\s*#00f2ff/)
  assert.match(src, /reportDeliverySweep/)
  assert.match(src, /reportDeliveryPulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('ReportList remains read-only and avoids forbidden product wording', () => {
  assert.doesNotMatch(apiSrc, /generateReport|reviewReport|publishReport|runDailyPipeline|finalizeReport|exportReport/)
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
