import { expect, test } from '@playwright/test'

import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const energyRows = [
  {
    business_date: '2026-06-05',
    workshop_code: '精整车间',
    shift_code: 'day',
    electricity_value: 1200,
    gas_value: 320,
    water_value: 18,
    total_energy: 660,
    output_weight: 34,
    energy_per_ton: 19.41
  },
  {
    business_date: '2026-06-05',
    workshop_code: '拉矫车间',
    shift_code: 'night',
    electricity_value: 300,
    gas_value: 120,
    water_value: 8,
    total_energy: 220,
    output_weight: 11,
    energy_per_ton: 20
  }
]

async function mockEnergySummary(page, scenario, options = {}) {
  const { requests = [] } = options
  await page.unroute('**/api/v1/energy/summary**')
  await page.route('**/api/v1/energy/summary**', async (route) => {
    requests.push(new URL(route.request().url()).searchParams.get('business_date'))

    if (scenario === 'forbidden') {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'review scope denied' })
      })
      return
    }

    if (scenario === 'unauthorized') {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'token expired' })
      })
      return
    }

    if (scenario === 'failed') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'energy summary failed' })
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(scenario === 'empty' ? [] : energyRows)
    })
  })
}

async function expectNoHorizontalOverflow(page) {
  await expect.poll(async () => {
    try {
      return await page.evaluate(() => Math.max(
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
        document.body.scrollWidth - document.body.clientWidth
      ))
    } catch (error) {
      if (String(error).includes('Execution context was destroyed')) return 999
      throw error
    }
  }).toBeLessThanOrEqual(1)
}

async function expectEnergyTableFits(page) {
  const table = page.getByTestId('energy-center-table')
  await expect(table).toBeVisible()
  const tableBox = await table.boundingBox()
  const lastHeaderBox = await table.evaluate((root) => {
    const visibleHeaders = Array.from(root.querySelectorAll('th'))
      .filter((header) => header.textContent.includes('单吨能耗'))
      .map((header) => {
        const rect = header.getBoundingClientRect()
        const style = window.getComputedStyle(header)
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) {
          return null
        }
        return { x: rect.x, width: rect.width }
      })
      .filter(Boolean)

    return visibleHeaders.at(-1) ?? null
  })

  expect(tableBox).not.toBeNull()
  expect(lastHeaderBox).not.toBeNull()
  expect(lastHeaderBox.x + lastHeaderBox.width).toBeLessThanOrEqual(tableBox.x + tableBox.width + 1)
}

async function openEnergyCenter(page, { scenario, viewport, requests = [] }) {
  await page.setViewportSize(viewport)
  await setupReviewSessionAndMocks(page)
  await mockEnergySummary(page, scenario, { requests })
  await page.goto('/manage/energy')

  await expect(page).toHaveURL(/\/manage\/energy/)
  await expect(page.getByTestId('energy-center-page')).toBeVisible()
  await expect(page.getByTestId('energy-center-status-bar')).toBeVisible()
  await expect(page.getByTestId('energy-center-stats')).toBeVisible()
  await expect(page.getByTestId('energy-center-flow')).toBeVisible()
  await expect(page.getByTestId('energy-event-rail')).toBeVisible()
  await expect(page.getByTestId('stitch-bottom-status')).toBeVisible()
}

async function expectEnergyValuesVisible(page, { table }) {
  const stats = page.getByTestId('energy-center-stats')
  for (const label of ['电耗', '气耗', '水耗', '总能耗', '产量', '单吨峰值']) {
    await expect(stats.getByText(label)).toBeVisible()
  }

  const detailSurface = table
    ? page.getByTestId('energy-center-table').locator('.el-table__body tbody tr').first()
    : page.getByTestId('energy-center-mobile-list').locator('article').first()

  await expect(detailSurface).toContainText('精整车间')
  await expect(detailSurface).toContainText('1,200')
  await expect(detailSurface).toContainText('320')
  await expect(detailSurface).toContainText('18')
  await expect(detailSurface).toContainText('660')
  await expect(detailSurface).toContainText('34')
  await expect(detailSurface).toContainText('19.41')

  if (table) {
    const cells = page.getByTestId('energy-center-table').locator('.el-table__body tbody tr').first().locator('td')
    await expect(cells.nth(3)).toContainText('1,200')
    await expect(cells.nth(4)).toContainText('320')
    await expect(cells.nth(5)).toContainText('18')
    await expect(cells.nth(6)).toContainText('660')
    await expect(cells.nth(7)).toContainText('34')
    await expect(cells.nth(8)).toContainText('19.41')
  } else {
    const grid = page.getByTestId('energy-center-mobile-list').locator('article').first().locator('.energy-center__mobile-grid')
    const labels = grid.locator('span')
    const values = grid.locator('strong')
    await expect(labels.nth(1)).toHaveText('电耗')
    await expect(values.nth(1)).toHaveText('1,200')
    await expect(labels.nth(4)).toHaveText('总能耗')
    await expect(values.nth(4)).toHaveText('660')
    await expect(labels.nth(6)).toHaveText('单吨能耗')
    await expect(values.nth(6)).toHaveText('19.41')
  }
}

test.describe('manage energy center Stitch surface', () => {
  for (const viewportCase of [
    { name: 'desktop', viewport: { width: 1440, height: 960 }, table: true },
    { name: 'mobile', viewport: { width: 720, height: 980 }, table: false }
  ]) {
    test(`${viewportCase.name} shows synced energy flow and source mapping`, async ({ page }) => {
      const pageErrors = []
      page.on('pageerror', (error) => pageErrors.push(error.message))

      await openEnergyCenter(page, { scenario: 'synced', viewport: viewportCase.viewport })

      const flow = page.getByTestId('energy-center-flow')
      await expect(flow.locator('.energy-center__flow-stage', { hasText: /^采集$/ })).toHaveCount(3)
      await expect(flow.locator('.energy-center__flow-stage', { hasText: /^折算$/ })).toBeVisible()
      await expect(flow.locator('.energy-center__flow-stage', { hasText: /^校核$/ })).toBeVisible()
      await expect(flow.getByText('能耗汇总接口').first()).toBeVisible()
      await expect(flow.getByText('算法汇总')).toBeVisible()
      await expect(flow.getByText('能耗明细字段')).toBeVisible()
      await expect(flow.locator('.energy-center__flow-card--result')).toBeVisible()
      await expect(flow.locator('.energy-center__flow-card--critical')).toBeVisible()
      await expect(flow.locator('.energy-center__flow-card--endpoint')).toHaveCount(2)

      await expect(page.getByText('已同步').first()).toBeVisible()
      await expect(page.getByText('页面刷新').first()).toBeVisible()
      await expect(page.getByText('精整车间 1,200 kWh')).toBeVisible()
      await expect(flow.getByText('拉矫车间 20 kgce/吨')).toBeVisible()
      await expect(page.getByTestId('energy-event-rail').getByText('拉矫车间 20 kgce/吨')).toBeVisible()
      await expect(page.getByTestId('energy-event-rail').getByRole('heading', { name: '能耗关注' })).toBeVisible()
      await expectEnergyValuesVisible(page, { table: viewportCase.table })

      if (viewportCase.table) {
        await expect(page.getByTestId('energy-center-table')).toBeVisible()
        await expect(page.getByTestId('energy-center-mobile-list')).toBeHidden()
        await expectEnergyTableFits(page)
      } else {
        await expect(page.getByTestId('energy-center-table')).toBeHidden()
        await expect(page.getByTestId('energy-center-mobile-list')).toBeVisible()
      }

      await expectNoHorizontalOverflow(page)
      expect(pageErrors).toEqual([])
    })

    test(`${viewportCase.name} keeps empty and failed states usable`, async ({ page }) => {
      await openEnergyCenter(page, { scenario: 'empty', viewport: viewportCase.viewport })

      await expect(page.getByText('待核').first()).toBeVisible()
      await expect(page.getByText('暂无能耗明细')).toBeVisible()
      await expectNoHorizontalOverflow(page)

      await mockEnergySummary(page, 'failed')
      await page.getByRole('button', { name: '刷新' }).click()

      await expect(page.getByTestId('energy-center-page')).toBeVisible()
      await expect(page.getByText('需核查').first()).toBeVisible()
      await expect(page.getByText('能耗数据需核查')).toBeVisible()
      await expectNoHorizontalOverflow(page)
    })
  }

  test('permission failure stays readable and does not look like successful sync', async ({ page }) => {
    await openEnergyCenter(page, { scenario: 'forbidden', viewport: { width: 1440, height: 960 } })

    await expect(page.getByTestId('energy-center-page')).toBeVisible()
    await expect(page.getByText('无权限查看能耗数据')).toBeVisible()
    await expect(page.getByText('需核查').first()).toBeVisible()
    await expect(page.getByText('已同步').first()).toBeHidden()
    await expectNoHorizontalOverflow(page)
  })

  test('unauthorized summary stays readable on the energy page', async ({ page }) => {
    await openEnergyCenter(page, { scenario: 'unauthorized', viewport: { width: 1440, height: 960 } })

    await expect(page).toHaveURL(/\/manage\/energy/)
    await expect(page.getByText('请先登录后查看能耗数据')).toBeVisible()
    await expect(page.getByText('需核查').first()).toBeVisible()
    await expect(page.getByText('已同步').first()).toBeHidden()
    await expectNoHorizontalOverflow(page)
  })

  test('changing business date reloads the summary with the selected date', async ({ page }) => {
    const requests = []
    await openEnergyCenter(page, {
      scenario: 'synced',
      viewport: { width: 1440, height: 960 },
      requests,
    })
    await expect.poll(() => requests.length).toBeGreaterThanOrEqual(1)

    const dateInput = page.locator('.energy-center__date input').first()
    await expect(dateInput).toBeVisible()
    await dateInput.click()
    await dateInput.fill('2026-06-04')
    await dateInput.press('Enter')

    await expect.poll(() => requests.at(-1)).toBe('2026-06-04')
    await expect(page.getByTestId('energy-center-status-bar')).toContainText('2026-06-04')
    await expectNoHorizontalOverflow(page)
  })
})
