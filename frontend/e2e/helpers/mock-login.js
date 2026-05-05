const DEFAULT_PASSWORD = 'playwright-password'

export async function loginThroughMockedPassword(page, {
  token,
  user,
  machineContext = null,
  username = '',
  password = DEFAULT_PASSWORD
}) {
  const loginUsername = username || user?.username || 'playwright-user'

  await page.route('**/api/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: token,
        token_type: 'bearer',
        user,
        machine_info: machineContext
      })
    })
  })

  await page.goto('/login')
  await page.getByTestId('login-username').fill(loginUsername)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await page.waitForURL(/\/(entry|manage|admin|team-lead)(?:\/|$)/, { timeout: 10000 })
}
