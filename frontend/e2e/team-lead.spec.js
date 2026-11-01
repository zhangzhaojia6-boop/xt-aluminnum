import { expect, test } from '@playwright/test'

import { setupUnifiedPerCoilEntrySession } from './helpers/unified-entry-mocks'

// 班长一屏已在 0ed58f6d 下线；旧通知里的 /team-lead 链接仍要能落到统一填报页
test('legacy team leader links open the unified entry', async ({ page }) => {
  await setupUnifiedPerCoilEntrySession(page)

  await page.goto('/team-lead')
  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()

  await page.goto('/team-lead/worker/102/2026-05-03?shift_id=1')
  await expect(page).toHaveURL(/\/entry\?shift_id=1$/)
  await expect(page.getByTestId('entry-shell')).toBeVisible()
})
