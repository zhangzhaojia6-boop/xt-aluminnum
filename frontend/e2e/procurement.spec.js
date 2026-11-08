import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const OUT = process.env.VISUAL_OUT || 'test-results/procurement'
const base = {
  id: 7, request_no: 'CG202611080007', material_name: '6205轴承', specification: '6205', unit: '个', category: '备品备件',
  quantity: '100', purchase_quantity: '80', estimated_unit_price: '100', amount: '8000.00', supplier: '洛阳轴承', is_emergency: false,
  status: 'open', current_step: 'purchase_approval', step_number: 6, step_label: '采购审批', step_role: 'general_manager',
  step_entered_at: '2026-11-08T09:00:00+08:00', deadline: null, is_overdue: false, can_act: true, trace_id: 't',
  purpose: '热轧检修', needed_by: '2026-11-20', details: {}, actions: ['approve', 'reject'],
  document_checklist: [
    { code: 'request_form', label: '物资采购/维修申请单', present: true },
    { code: 'comparison', label: '采购比价表或询价豁免审批单', present: true },
    { code: 'contract', label: '审核签订的采购合同或采购订单', present: false },
    { code: 'invoice', label: '增值税发票', present: false },
  ],
  documents: [], quotes: [
    { round_no: 1, supplier: '洛阳轴承', unit_price: '100', is_selected: true },
    { round_no: 1, supplier: '郑州五金', unit_price: '118', is_selected: false },
  ],
  logs: [{ step: 'draft', step_label: '提报需求', action: 'submit', actor_name: '统计员', at: '2026-11-08T08:00:00+08:00' }],
}

async function mockProcurement(page, { enabled = true } = {}) {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/procurement/**', (route) => {
    const url = route.request().url()
    if (!enabled) return route.fulfill({ status: 404, json: { detail: '采购模块未开启' } })
    if (url.includes('/meta')) return route.fulfill({ json: { roles: ['general_manager'], can_view_all: true, can_manage: true, can_edit_suppliers: true, enabled: true, steps: [{ code: 'quotation', label: '询价比价' }], categories: ['原材料', '备品备件', '设备配件', '工装工具', '劳保用品', '维修耗材'], assignable_roles: { general_manager: '总经理', legal: '法务' } } })
    if (url.includes('/assignments')) return route.fulfill({ json: [{ id: 1, user_id: 3, user_name: '周总', role: 'general_manager', role_label: '总经理' }] })
    if (url.includes('/board')) return route.fulfill({ json: { open_count: 12, overdue_count: 2, emergency_count: 1, archived_count: 30, stock_closed_count: 9, month_paid_amount: '186000.00', funnel: Array.from({ length: 16 }, (_, i) => ({ number: i + 1, label: `环节${i + 1}`, count: (i * 3) % 5 })), overdue: [{ ...base, is_overdue: true }], split_warnings: [{ material_name: '轴承', supplier: '甲', total_amount: '5500', request_nos: ['A', 'B'] }], emergency_backfill_overdue: 1, month_by_category: [{ category: '备品备件', amount: '86000.00' }, { category: '劳保用品', amount: '12000.00' }], top_suppliers: [{ supplier: '洛阳轴承', amount: '66000.00' }, { supplier: '郑州五金', amount: '32000.00' }], step_hours: [{ step: 'quotation', label: '询价比价', hours: 30.5, count: 4 }, { step: 'purchase_approval', label: '采购审批', hours: 6, count: 4 }] } })
    if (url.includes('/ledger')) return route.fulfill({ json: { items: [{ ...base, requester_name: '统计员', workshop_name: '热轧', created_at: '2026-11-08T08:00:00+08:00' }, { ...base, id: 8, status: 'archived', requester_name: '统计员', workshop_name: '冷轧', is_emergency: true, backfill_due_on: '2026-11-12', created_at: '2026-11-07T08:00:00+08:00' }], total: 45, page: 1, page_size: 20, total_amount: '186000.00' } })
    if (url.includes('/suppliers')) return route.fulfill({ json: [{ id: 1, name: '洛阳轴承', status: 'qualified', contact: '0379', remark: '', quote_count: 8, win_count: 5, total_amount: '66000.00' }, { id: 2, name: '假冒公司', status: 'blacklisted', contact: '', remark: '以次充好', quote_count: 1, win_count: 0, total_amount: '0' }] })
    if (url.endsWith('/actions')) return route.fulfill({ json: { ...base, current_step: 'contract_draft', step_number: 7, step_label: '拟定合同', can_act: false } })
    if (/\/requests\/7/.test(url)) return route.fulfill({ json: base })
    if (url.includes('/requests')) return route.fulfill({ json: [base, { ...base, id: 8, is_overdue: true, material_name: '液压油', amount: '3200.00' }] })
    return route.fulfill({ json: {} })
  })
}

for (const [label, width, height] of [['desktop', 1440, 900], ['mobile', 375, 812]]) {
  test(`procurement pages ${label}`, async ({ page }) => {
    await mockProcurement(page)
    await page.setViewportSize({ width, height })

    await page.goto('/procurement')
    await expect(page.getByTestId('procurement-row')).toHaveCount(2)
    await page.screenshot({ path: `${OUT}/list-${label}.png` })

    await page.goto('/procurement/new')
    await expect(page.getByTestId('procurement-form')).toBeVisible()
    await page.getByTestId('pc-quantity').fill('20')
    await page.getByTestId('pc-price').fill('100')
    await expect(page.getByTestId('pc-total')).toHaveText('¥2,000')
    await page.screenshot({ path: `${OUT}/new-${label}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

    await page.goto('/procurement/7')
    await expect(page.getByTestId('procurement-status')).toContainText('第 6 步')
    await expect(page.getByTestId('procurement-track').locator('.is-done')).toHaveCount(5)
    await page.screenshot({ path: `${OUT}/detail-${label}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

    await page.goto('/procurement/board')
    await expect(page.getByTestId('procurement-funnel').locator('li')).toHaveCount(16)
    await expect(page.getByTestId('procurement-split')).toContainText('轴承')
    await expect(page.getByTestId('procurement-backfill')).toContainText('1')
    await page.screenshot({ path: `${OUT}/board-${label}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

    await page.goto('/procurement/ledger?emergency=true')
    await expect(page.getByTestId('ledger-row')).toHaveCount(2)
    await expect(page.getByTestId('ledger-emergency')).toBeChecked()
    await expect(page.getByTestId('ledger-total')).toHaveText('¥186,000.00')
    await page.screenshot({ path: `${OUT}/ledger-${label}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

    await page.goto('/procurement/suppliers')
    await expect(page.getByTestId('supplier-row')).toHaveCount(2)
    await page.screenshot({ path: `${OUT}/suppliers-${label}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

    await page.goto('/procurement/staff')
    await expect(page.getByTestId('procurement-assignments')).toContainText('周总')
    await expect(page.getByTestId('procurement-assignments')).toContainText('未指派')
    await page.screenshot({ path: `${OUT}/staff-${label}.png`, fullPage: true })

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  })
}

test('approve sends the step it was looking at', async ({ page }) => {
  await mockProcurement(page)
  await page.goto('/procurement/7')
  const posted = page.waitForRequest((request) => request.url().endsWith('/actions'))
  await page.getByTestId('pc-approve').click()
  const body = (await posted).postDataJSON()
  expect(body.action).toBe('approve')
  expect(body.expected_step).toBe('purchase_approval')
  await expect(page.getByTestId('procurement-status')).toContainText('拟定合同')
  await expect(page.getByTestId('procurement-panel')).toHaveCount(0)
})

test('disabled module shows a calm empty state', async ({ page }) => {
  await mockProcurement(page, { enabled: false })
  await page.goto('/procurement')
  await expect(page.getByTestId('procurement-disabled')).toBeVisible()
  await expect(page.getByTestId('procurement-row')).toHaveCount(0)
})
