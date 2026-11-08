import { expect, test } from '@playwright/test'

// 真实后端走单。需要已灌好账号的后端，默认跳过：PROCUREMENT_REAL=1 才跑。
const API = process.env.PROCUREMENT_API || 'http://127.0.0.1:8000/api/v1'
const PASSWORD = process.env.PROCUREMENT_PASSWORD || 'Pilot#2026'
const FILE = { name: 'doc.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 pilot') }
const ACCOUNTS = {
  requester: 'pilot-requester',
  workshop_director: 'pilot-director',
  equipment: 'pilot-equipment',
  warehouse: 'pilot-warehouse',
  purchasing: 'pilot-purchasing',
  purchasing_lead: 'pilot-purchasing-lead',
  division_lead: 'pilot-division-lead',
  general_manager: 'pilot-general-manager',
  legal: 'pilot-legal',
  finance: 'pilot-finance',
  accountant: 'pilot-accountant',
  gate: 'pilot-gate',
  quality: 'pilot-quality',
  audit: 'pilot-audit',
}

test.skip(process.env.PROCUREMENT_REAL !== '1', '需要真实后端')
test.describe.configure({ timeout: 300000 })

const tokens = new Map()

async function tokenOf(request, role) {
  if (!tokens.has(role)) {
    const login = () => request.post(`${API}/auth/login`, { data: { username: ACCOUNTS[role], password: PASSWORD } })
    let res = await login()
    if (res.status() === 429) {
      await new Promise((resolve) => setTimeout(resolve, 61000))
      res = await login()
    }
    expect(res.ok(), `${role} 登录 ${res.status()}`).toBeTruthy()
    tokens.set(role, (await res.json()).access_token)
  }
  return tokens.get(role)
}

async function openAs(page, token, path) {
  await page.addInitScript((value) => localStorage.setItem('aluminum_bypass_token', value), token)
  await page.goto(path)
}

async function fetchRequest(request, token, id) {
  const res = await request.get(`${API}/procurement/requests/${id}`, { headers: { Authorization: `Bearer ${token}` } })
  expect(res.ok()).toBeTruthy()
  return res.json()
}

async function act(page, step, scenario) {
  const panel = page.getByTestId('procurement-panel')
  await expect(panel).toBeVisible()
  const click = (name) => panel.getByRole('button', { name, exact: true }).click()
  const fill = (label, value) => panel.getByLabel(label, { exact: true }).fill(String(value))
  const attach = async (label) => {
    const posted = page.waitForResponse((res) => res.url().includes('/documents') && res.request().method() === 'POST')
    await panel.getByLabel(label).setInputFiles(FILE)
    expect((await posted).ok()).toBeTruthy()
  }

  if (step === 'draft') return click('提交审批')
  if (step === 'stock_review') {
    await fill('库存数量', 0)
    return click('确认库存')
  }
  if (step === 'quotation') {
    for (let index = 1; index < scenario.quotes.length; index += 1) await click('再加一家')
    const suppliers = panel.getByLabel('供应商', { exact: true })
    const prices = panel.getByLabel('单价', { exact: true })
    for (const [index, price] of scenario.quotes.entries()) {
      await suppliers.nth(index).fill(`供应商${index + 1}`)
      await prices.nth(index).fill(String(price))
    }
    return click('提交比价')
  }
  if (step === 'contract_draft') {
    if (scenario.docKind === 'contract') await attach('上传合同稿')
    await fill('编号', 'HT-001')
    await fill('金额（元）', scenario.amount)
    return click('提交审核')
  }
  if (step === 'finance_contract_review') {
    await fill('签约主体', '河南鑫泰铝业有限公司')
    return click('同意')
  }
  if (step === 'contract_sign') {
    if (scenario.docKind === 'contract') await attach('上传盖章合同')
    return click('确认已签订，可以供货')
  }
  if (step === 'gate_registration') {
    await fill('送货单位', '供应商1')
    await fill('货物名称', scenario.material)
    await fill('数量', scenario.quantity)
    await fill('车牌号', '豫A12345')
    return click('生成到货单')
  }
  if (step === 'acceptance') {
    await attach('上传供应商送货单')
    await fill('验收数量', scenario.quantity)
    if (scenario.needsQuality) await panel.getByLabel('需要质检（生产物料、关键备件）').check()
    return click('验收合格，生成入库单')
  }
  if (step === 'document_collection') {
    await attach('上传增值税发票')
    await fill('发票号', 'FP-001')
    await fill('发票金额', scenario.amount)
    await fill('付款金额', scenario.amount)
    return click('发起付款')
  }
  if (step === 'payment_booking') {
    await fill('凭证号', 'PZ-001')
    return click('登记付款并归档')
  }
  return click('同意')
}

async function runScenario(page, browser, request, scenario) {
  const requesterToken = await tokenOf(request, 'requester')
  await openAs(page, requesterToken, '/procurement/new')
  await page.getByTestId('pc-material').fill(scenario.material)
  await page.getByRole('radio', { name: scenario.category }).check({ force: true })
  await page.getByTestId('pc-quantity').fill(String(scenario.quantity))
  await page.getByTestId('pc-unit').fill('个')
  await page.getByTestId('pc-price').fill(String(scenario.price))
  await page.getByTestId('pc-purpose').fill('试点')
  await page.getByTestId('pc-save').click()
  await page.waitForURL(/\/procurement\/\d+$/)
  const id = Number(page.url().split('/').pop())

  const walked = []
  for (let guard = 0; guard < 30; guard += 1) {
    const current = await fetchRequest(request, requesterToken, id)
    if (current.status !== 'open') break
    const role = current.step_role
    walked.push(current.current_step)
    const context = await browser.newContext()
    const actor = await context.newPage()
    const failed = []
    actor.on('response', (res) => { if (res.url().includes('/api/') && res.status() >= 400) failed.push(`${res.status()} ${res.url()}`) })
    await openAs(actor, await tokenOf(request, role), `/procurement/${id}`)
    await act(actor, current.current_step, scenario)
    await expect.poll(async () => (await fetchRequest(request, requesterToken, id)).current_step + (await fetchRequest(request, requesterToken, id)).status, { timeout: 15000, message: `${current.current_step} 没有往下走 ${failed.join(';')}` })
      .not.toBe(current.current_step + current.status)
    expect(failed, `${current.current_step} 的接口错误`).toEqual([])
    await context.close()
  }
  return { id, walked, final: await fetchRequest(request, requesterToken, id) }
}

test('5000 元以下走订单路径', async ({ page, browser, request }) => {
  const { walked, final } = await runScenario(page, browser, request, {
    material: '手套', category: '劳保用品', quantity: 10, price: 100, amount: 1000, quotes: [100], docKind: 'order', needsQuality: false,
  })
  expect(final.status).toBe('archived')
  expect(walked).toEqual(['draft', 'workshop_approval', 'stock_review', 'quotation', 'purchase_approval', 'contract_draft', 'finance_contract_review', 'contract_sign', 'gate_registration', 'acceptance', 'document_collection', 'payment_review', 'payment_approval', 'payment_booking'])
  expect(final.document_checklist.every((doc) => doc.present || doc.code === 'payment_request')).toBe(true)
})

test('5 万元以上走合同、技术审核、法务和质检', async ({ page, browser, request }) => {
  const { walked, final } = await runScenario(page, browser, request, {
    material: '轴承', category: '设备配件', quantity: 600, price: 100, amount: 60000, quotes: [100, 110, 120], docKind: 'contract', needsQuality: true,
  })
  expect(final.status).toBe('archived')
  expect(walked).toEqual(['draft', 'workshop_approval', 'tech_review', 'stock_review', 'quotation', 'quotation_confirm', 'purchase_approval', 'contract_draft', 'legal_review', 'finance_contract_review', 'contract_sign', 'gate_registration', 'acceptance', 'quality_check', 'document_collection', 'payment_review', 'payment_approval', 'payment_booking'])
  expect(final.documents.length).toBeGreaterThanOrEqual(4)
})

test('后台：采购科负责人拉黑，企管筛选并导出，门岗看不到', async ({ page, browser, request }) => {
  const leadPage = await (await browser.newContext()).newPage()
  await openAs(leadPage, await tokenOf(request, 'purchasing_lead'), '/procurement/suppliers')
  await leadPage.getByTestId('supplier-add').click()
  await leadPage.getByTestId('supplier-name').fill('黑名单测试公司')
  await leadPage.getByTestId('supplier-status').selectOption('blacklisted')
  await leadPage.getByTestId('supplier-save').click()
  await expect(leadPage.getByTestId('supplier-row').filter({ hasText: '黑名单测试公司' })).toContainText('黑名单')

  const auditPage = await (await browser.newContext()).newPage()
  await openAs(auditPage, await tokenOf(request, 'audit'), '/procurement/ledger')
  await expect(auditPage.getByTestId('ledger-row').first()).toBeVisible()
  await auditPage.getByTestId('ledger-keyword').fill('轴承')
  await auditPage.getByTestId('ledger-apply').click()
  await expect(auditPage.getByTestId('ledger-row').first()).toContainText('轴承')
  await expect(auditPage.getByTestId('ledger-row').filter({ hasText: '手套' })).toHaveCount(0)
  const download = auditPage.waitForEvent('download')
  await auditPage.getByTestId('ledger-export').click()
  expect((await download).suggestedFilename()).toContain('采购台账')
  await expect(auditPage.getByTestId('supplier-form')).toHaveCount(0)
  await auditPage.goto('/procurement/board')
  await expect(auditPage.getByTestId('procurement-hours')).toBeVisible()

  const gatePage = await (await browser.newContext()).newPage()
  await openAs(gatePage, await tokenOf(request, 'gate'), '/procurement/ledger')
  await expect(gatePage.getByText('没有查看全部台账的权限')).toBeVisible()
  await expect(gatePage.getByRole('link', { name: '总览' })).toHaveCount(0)
})
