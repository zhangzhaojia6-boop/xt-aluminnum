import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test('manage coils page shows MES coil trace and machine binding state', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.goto('/manage/coils', { waitUntil: 'domcontentloaded' })

  await expect(page).toHaveURL(/\/manage\/coils$/)
  await expect(page.getByTestId('manage-shell')).toBeVisible()
  await expect(page.getByTestId('manage-coils')).toBeVisible()
  await expect(page.getByRole('heading', { name: '卷级线索' })).toBeVisible()
  await expect(page.getByPlaceholder('搜索随行卡、批号、合金、机列')).toBeVisible()

  await expect(page.getByTestId('manage-coils-table')).toContainText('TK-20260423-001')
  await expect(page.getByTestId('manage-coils-table')).toContainText('XT-ZD-1')
  await expect(page.getByTestId('manage-coils-table')).toContainText('待绑定')
  await expect(page.getByTestId('manage-coils-table')).toContainText('0.35 吨')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('MES 主数据')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('MES 上机')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('MES 下机')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('自动废料')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('6.35 吨')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('人工补录对照')
  await expect(page.getByTestId('manage-coils-flow')).toContainText('补录不覆盖 MES 原始记录')

  await page.getByPlaceholder('筛选客户').fill('中原')
  await page.getByPlaceholder('当前工艺').fill('包装')
  await page.getByLabel('筛选机列状态').selectOption('pending')

  await expect(page.getByTestId('manage-coils-filter-summary')).toContainText('1 / 2 卷')
  await expect(page.getByTestId('manage-coils-table')).toContainText('TK-20260423-002')
  await expect(page.getByTestId('manage-coils-table')).toContainText('中原客户')
  await expect(page.getByTestId('manage-coils-table')).toContainText('0.96*1220*C')
  await expect(page.getByTestId('manage-coils-table')).not.toContainText('TK-20260423-001')
})

test('manage coils page stays usable on a narrow factory screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setupReviewSessionAndMocks(page)
  await page.goto('/manage/coils?desktop=1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByTestId('manage-coils')).toBeVisible()
  await expect(page.getByPlaceholder('筛选客户')).toBeVisible()
  await expect(page.getByLabel('筛选机列状态')).toBeVisible()

  await page.getByPlaceholder('筛选客户').fill('中原')
  await page.getByLabel('筛选机列状态').selectOption('pending')

  await expect(page.getByTestId('manage-coils-filter-summary')).toContainText('1 / 2 卷')
  await expect(page.getByTestId('manage-coils-table')).toContainText('TK-20260423-002')

  const overflow = await page.evaluate(() => Math.max(
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
    document.body.scrollWidth - document.body.clientWidth,
  ))
  expect(overflow).toBeLessThanOrEqual(1)
})
