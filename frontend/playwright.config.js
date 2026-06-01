import { defineConfig, devices } from '@playwright/test'

import fs from 'node:fs'
import path from 'node:path'

import { shouldIgnoreHttpsErrors } from './e2e/helpers/tls.js'

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

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173'
const backendURL = process.env.PLAYWRIGHT_BACKEND_URL || 'http://localhost:8000'
const reuseServers = process.env.PLAYWRIGHT_REUSE_SERVERS === '1'
const skipWebServers = process.env.PLAYWRIGHT_SKIP_WEB_SERVER === '1'

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  globalSetup: './e2e/global-setup.js',
  fullyParallel: false,
  workers: process.env.PLAYWRIGHT_WORKERS ? Number(process.env.PLAYWRIGHT_WORKERS) : 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL,
    headless: true,
    ignoreHTTPSErrors: shouldIgnoreHttpsErrors({ baseURL }),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: skipWebServers ? undefined : [
    {
      name: 'backend',
      command: process.platform === 'win32'
        ? 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_e2e_backend.ps1'
        : 'bash scripts/start_e2e_backend.sh',
      cwd: '../backend',
      url: `${backendURL}/healthz`,
      reuseExistingServer: reuseServers,
      timeout: 120000,
      stdout: 'pipe',
      stderr: 'pipe'
    },
    {
      name: 'frontend',
      command: 'npm run build && npm run preview',
      url: baseURL,
      reuseExistingServer: reuseServers,
      timeout: 120000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        ...process.env,
        VITE_PLAYWRIGHT_STORAGE_STATE: '1',
        VITE_API_PROXY_TARGET: backendURL
      }
    }
  ],
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json'
      }
    },
    {
      name: 'mobile',
      testMatch: [
        /.*mobile-.*\.spec\.js/,
        /.*dynamic-entry-layout\.spec\.js/,
        /.*team-lead\.spec\.js/,
        /.*zd1-machine-smoke\.spec\.js/
      ],
      use: {
        ...devices['Pixel 5']
      }
    }
  ]
})
