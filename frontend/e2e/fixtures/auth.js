import { test as base } from '@playwright/test'
import path from 'node:path'
import fs from 'node:fs'

/**
 * Authentication Fixture for Playwright
 * Handles automatic login and session state persistence
 */

export const test = base.extend({
  // This fixture will provide a logged-in page
  authenticatedPage: async ({ page }, use) => {
    const authFile = path.resolve('e2e/.auth/user.json')
    
    // Check if we have a valid session
    if (fs.existsSync(authFile)) {
      await page.context().addCookies(JSON.parse(fs.readFileSync(authFile, 'utf8')).cookies)
    } else {
      // Perform login
      await page.goto('/login')
      await page.fill('[data-testid="username-input"]', process.env.PLAYWRIGHT_USERNAME || 'admin')
      await page.fill('[data-testid="password-input"]', process.env.PLAYWRIGHT_PASSWORD || 'admin123')
      await page.click('[data-testid="login-submit"]')
      
      // Wait for navigation to dashboard
      await page.waitForURL('**/dashboard/**')
      
      // Save state
      const storage = await page.context().storageState()
      if (!fs.existsSync(path.dirname(authFile))) {
        fs.mkdirSync(path.dirname(authFile), { recursive: true })
      }
      fs.writeFileSync(authFile, JSON.stringify(storage))
    }
    
    await use(page)
  }
})

export { expect } from '@playwright/test'
