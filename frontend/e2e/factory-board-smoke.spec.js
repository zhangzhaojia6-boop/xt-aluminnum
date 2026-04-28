import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'

async function login(page) {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/dashboard\/factory/)
}

test('review factory board renders the compact native Element Plus surface', async ({ page }) => {
  await login(page)
  await page.goto('/review/factory')

  const board = page.getByTestId('factory-dashboard')
  await expect(page).toHaveURL(/\/review\/factory/)
  await expect(board).toBeVisible()
  await expect(board.getByRole('heading', { name: '工厂作业看板' })).toBeVisible()
  await expect(board.getByText('今日产量')).toBeVisible()
  await expect(board.getByText('今日上报状态')).toBeVisible()
  await expect(board.getByTestId('delivery-ready-card')).toBeVisible()
  await expect(board.getByTestId('delivery-missing-steps')).toBeVisible()
  await expect(board.getByText('智能体联动')).toHaveCount(0)
  await expect(board.getByText('鑫泰铝业协同运营平台')).toHaveCount(0)
})
