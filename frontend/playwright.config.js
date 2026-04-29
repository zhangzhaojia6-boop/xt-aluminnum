import { defineConfig } from '@playwright/test'

import fs from 'node:fs'
import path from 'node:path'

function loadLocalEnvFallbacks() {
  const envPath = path.resolve('..', '.env')
  if (!fs.existsSync(envPath)) return

  const entries = fs.readFileSync(envPath, 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))

  for (const line of entries) {
    const separator = line.indexOf('=')
    if (separator === -1) continue
    const key = line.slice(0, separator).trim()
    const value = line.slice(separator + 1).trim().replace(/^['"]|['"]$/g, '')
    if (key === 'INIT_ADMIN_USERNAME' && !process.env.PLAYWRIGHT_USERNAME) {
      process.env.PLAYWRIGHT_USERNAME = value
    }
    if (key === 'INIT_ADMIN_PASSWORD' && !process.env.PLAYWRIGHT_PASSWORD) {
      process.env.PLAYWRIGHT_PASSWORD = value
    }
    if (key === 'INIT_ADMIN_USERNAME' && !process.env.PLAYWRIGHT_ADMIN_USERNAME) {
      process.env.PLAYWRIGHT_ADMIN_USERNAME = value
    }
    if (key === 'INIT_ADMIN_PASSWORD' && !process.env.PLAYWRIGHT_ADMIN_PASSWORD) {
      process.env.PLAYWRIGHT_ADMIN_PASSWORD = value
    }
  }
}

loadLocalEnvFallbacks()

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: false,
  workers: process.env.PLAYWRIGHT_WORKERS ? Number(process.env.PLAYWRIGHT_WORKERS) : 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'https://localhost',
    headless: true,
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  }
})
