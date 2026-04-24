import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.beforeEach(async ({ page }) => {
  await setupReviewSessionAndMocks(page)
})

test('review shell keeps the redesigned home readable across desktop tablet and mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('review-brand-mark')).toBeVisible()
  await expect(page.getByTestId('review-brand-title')).toContainText('鑫泰铝业')
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('review-command-deck')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()

  await page.setViewportSize({ width: 900, height: 1180 })
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('review-command-deck')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()

  await page.setViewportSize({ width: 430, height: 932 })
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('review-command-deck')).toBeVisible()
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
})

test('factory review home shows twin-core hero and expandable assistant workbench', async ({ page }) => {
  await page.goto('/review/factory')

  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('review-command-deck')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()

  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
  await page.getByRole('button', { name: '打开 AI 助手' }).click()
  await expect(page.getByTestId('review-assistant-workbench')).toBeVisible()
  await expect(page.getByRole('button', { name: /问答|开始问答/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /取数|搜上下文/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /图卡|出图/ })).toBeVisible()
  const capabilityHeadings = page.locator('.review-assistant-workbench__capability-top h3')
  await expect(capabilityHeadings.first()).toBeVisible()
  expect(await capabilityHeadings.count()).toBeGreaterThanOrEqual(3)
})
