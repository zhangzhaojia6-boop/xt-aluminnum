import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/inventory/InventoryCenter.vue')
const src = fs.readFileSync(pagePath, 'utf8')

test('InventoryCenter keeps the real inventory data and export paths', () => {
  assert.match(src, /api\.get\(['"]\/inventory\/summary['"]/)
  assert.match(src, /date_from:\s*dateRange\.value\?\.\[0\]/)
  assert.match(src, /date_to:\s*dateRange\.value\?\.\[1\]/)
  assert.match(src, /warehouse_id:\s*warehouseFilter\.value\s*\|\|\s*undefined/)
  assert.match(src, /data\.warehouses\s*\|\|\s*warehouses\.value/)
  assert.match(src, /api\.get\(['"]\/inventory\/export['"]/)
  assert.match(src, /responseType:\s*['"]blob['"]/)
  assert.match(src, /downloadBlob\(data,\s*['"]inventory_summary\.csv['"]\)/)
  assert.doesNotMatch(src, /window\.open\(`\/api\/v1\/inventory\/export/)
})

test('InventoryCenter keeps all KPI fields and ton units visible', () => {
  for (const field of ['current_stock', 'stock_change', 'inbound_today', 'outbound_today', 'anomaly_count']) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['当前库存', '今日入库', '今日出库', '异动告警', '吨']) {
    assert.match(src, new RegExp(label))
  }
})

test('InventoryCenter keeps trend and transaction table fields visible', () => {
  assert.match(src, /trendSeries/)
  assert.match(src, /trendLabels/)
  assert.match(src, /data\.transactions/)
  assert.match(src, /data-source="inventory_transactions"/)

  for (const field of ['transaction_date', 'warehouse_name', 'material_name', 'direction', 'quantity', 'operator']) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['日期', '仓库', '物料', '方向', '数量\\(吨\\)', '操作人']) {
    assert.match(src, new RegExp(label))
  }
})

test('InventoryCenter uses the industrial blue responsive surface', () => {
  assert.match(src, /data-testid="inventory-center-page"/)
  assert.match(src, /data-testid="inventory-center-filters"/)
  assert.match(src, /data-testid="inventory-center-stats"/)
  assert.match(src, /data-testid="inventory-center-table"/)
  assert.match(src, /data-testid="inventory-center-mobile-list"/)
  assert.match(src, /库存管控/)
  assert.match(src, /库存流转/)
  assert.match(src, /出入库流水/)
  assert.match(src, /--inventory-cyan:\s*#00f2ff/)
  assert.match(src, /inventorySweep/)
  assert.match(src, /inventoryPulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('InventoryCenter avoids write operations and forbidden product wording', () => {
  assert.doesNotMatch(src, /createInventory|updateInventory|deleteInventory|approveInventory|publishInventory/)
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
