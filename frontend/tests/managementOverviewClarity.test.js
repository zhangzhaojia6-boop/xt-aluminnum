import test from 'node:test'
import assert from 'node:assert/strict'

import { buildManagementOverview, marginTone } from '../src/utils/managementOverview.js'

test('buildManagementOverview exposes management first-screen metrics', () => {
  const overview = buildManagementOverview({
    aggregation: {
      overall_progress: {
        submitted_cells: 6,
        total_cells: 8,
        missing_cell_count: 2,
        attention_cell_count: 1,
      },
      factory_total: {
        input: 220,
        output: 214,
        scrap: 6,
        yield_rate: 97.27,
      },
    },
    dashboard: {
      management_estimate: {
        estimate_ready: true,
        estimated_revenue: 280000,
        estimated_cost: 210000,
        estimated_margin: 70000,
      },
      exception_lane: {
        returned_shift_count: 1,
        mobile_exception_count: 1,
        production_exception_count: 1,
        reminder_late_count: 1,
        reconciliation_open_count: 1,
        pending_report_publish_count: 1,
      },
      leader_metrics: {
        storage_finished_weight: 52,
        shipment_weight: 48,
      },
    },
    delivery: {
      delivery_ready: false,
      missing_steps: ['日报未生成'],
    },
  })

  assert.equal(overview.outputWeight, 214)
  assert.equal(overview.lossWeight, 6)
  assert.equal(overview.lossRate, 2.73)
  assert.equal(overview.yieldRate, 97.27)
  assert.equal(overview.estimatedMargin, 70000)
  assert.deepEqual(overview.blockerBreakdown, {
    missingCells: 2,
    attentionCells: 1,
    anomalyCount: 5,
    deliveryBlocker: 1,
    pendingPublish: 1,
  })
  assert.equal(overview.blockerCount, 9)
  assert.equal(overview.deliveryReady, false)
  assert.equal(overview.storageFinishedWeight, 52)
  assert.equal(overview.shipmentWeight, 48)
})

test('buildManagementOverview falls back cleanly when estimate is not configured', () => {
  const overview = buildManagementOverview({
    aggregation: {
      factory_total: { output: 12, scrap: 0, yield_rate: null },
      overall_progress: { submitted_cells: 1, total_cells: 1 },
    },
    dashboard: {
      leader_metrics: {
        estimated_revenue: 1000,
        estimated_cost: 800,
        estimated_margin: 200,
      },
    },
    delivery: { delivery_ready: true },
  })

  assert.equal(overview.estimateReady, false)
  assert.equal(overview.estimatedMargin, null)
  assert.equal(overview.marginLabel, '待配置')
  assert.equal(marginTone(null), 'muted')
})

test('buildManagementOverview explains blockers by missing, anomalies, delivery, and publish work', () => {
  const overview = buildManagementOverview({
    aggregation: {
      overall_progress: {
        submitted_cells: 7,
        total_cells: 10,
        attention_cell_count: 2,
      },
    },
    dashboard: {
      exception_lane: {
        returned_shift_count: 2,
        mobile_exception_count: 1,
        production_exception_count: 6,
        reminder_late_count: 3,
        reconciliation_open_count: 4,
        pending_report_publish_count: 5,
      },
    },
    delivery: {
      delivery_ready: false,
    },
  })

  assert.deepEqual(overview.blockerBreakdown, {
    missingCells: 3,
    attentionCells: 2,
    anomalyCount: 16,
    deliveryBlocker: 1,
    pendingPublish: 5,
  })
  assert.equal(overview.blockerCount, 25)
})

test('marginTone maps operating estimate to readable states', () => {
  assert.equal(marginTone(100), 'success')
  assert.equal(marginTone(0), 'neutral')
  assert.equal(marginTone(-1), 'danger')
  assert.equal(marginTone(null), 'muted')
})
