import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/contracts/ContractsCenter.vue')
const src = fs.readFileSync(pagePath, 'utf8')

test('ContractsCenter keeps the real contracts data and export paths', () => {
  assert.match(src, /api\.get\(['"]\/contracts\/summary['"]/)
  assert.match(src, /date_from:\s*dateRange\.value\?\.\[0\]/)
  assert.match(src, /date_to:\s*dateRange\.value\?\.\[1\]/)
  assert.match(src, /status:\s*statusFilter\.value\s*\|\|\s*undefined/)
  assert.match(src, /api\.get\(['"]\/contracts\/export['"]/)
  assert.match(src, /responseType:\s*['"]blob['"]/)
  assert.match(src, /downloadBlob\(data,\s*['"]contracts_summary\.csv['"]\)/)
  assert.doesNotMatch(src, /window\.open\(`\/api\/v1\/contracts\/export/)
})

test('ContractsCenter keeps all KPI fields and ton units visible', () => {
  for (const field of ['active_count', 'fulfillment_pct', 'overdue_count', 'mtd_delivery_tons']) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['活跃合同', '履约率', '延期预警', '本月交付量', '吨']) {
    assert.match(src, new RegExp(label))
  }
})

test('ContractsCenter keeps every contract table field visible', () => {
  for (const field of [
    'contract_no',
    'customer_name',
    'total_quantity',
    'delivered_quantity',
    'progress_pct',
    'deadline',
    'status'
  ]) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['合同号', '客户', '合同量\\(吨\\)', '已交付\\(吨\\)', '进度', '交期', '状态']) {
    assert.match(src, new RegExp(label))
  }
})

test('ContractsCenter uses the industrial blue responsive surface', () => {
  assert.match(src, /data-testid="contracts-center-page"/)
  assert.match(src, /data-testid="contracts-center-filters"/)
  assert.match(src, /data-testid="contracts-center-stats"/)
  assert.match(src, /data-testid="contracts-center-table"/)
  assert.match(src, /data-testid="contracts-center-mobile-list"/)
  assert.match(src, /ORDER CONTROL/)
  assert.match(src, /FULFILLMENT FLOW/)
  assert.match(src, /CONTRACT MATRIX/)
  assert.match(src, /--contracts-cyan:\s*#00f2ff/)
  assert.match(src, /contractsSweep/)
  assert.match(src, /contractsPulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('ContractsCenter avoids write operations and forbidden product wording', () => {
  assert.doesNotMatch(src, /createContract|updateContract|deleteContract|approveContract|publishContract/)
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
