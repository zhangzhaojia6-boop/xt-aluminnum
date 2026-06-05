import { expect, test } from '@playwright/test'

import { setupReviewSessionAndMocks } from './helpers/review-mocks'

const adminUser = {
  id: 1,
  username: 'admin',
  name: 'Playwright Admin',
  role: 'admin',
  is_mobile_user: true,
  is_reviewer: true,
  is_manager: true,
  data_scope_type: 'all',
  assigned_shift_ids: [],
}

test('retired workshop template center redirects to system settings', async ({ page }) => {
  await setupReviewSessionAndMocks(page, {
    token: 'playwright-admin-token',
    user: adminUser,
  })

  await page.goto('/manage/admin/templates')

  await expect(page).toHaveURL(/\/manage\/admin\/settings$/)
  await expect(page.getByTestId('system-settings-page')).toBeVisible()
  await expect(page.getByTestId('template-editor-page')).toHaveCount(0)
  await expect(page.getByRole('navigation', { name: '系统设置入口' })).toBeVisible()
})
