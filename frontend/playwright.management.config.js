import { defineConfig } from '@playwright/test'

const baseURL = process.env.DASHBOARD_URL || 'http://127.0.0.1:4185'

export default defineConfig({
  testDir: './e2e',
  testMatch: ['management-fact-display.spec.js', 'management-workspace.spec.js', 'manage-shell.spec.js'],
  outputDir: './test-results/management',
  timeout: 45000,
  workers: 1,
  reporter: 'list',
  use: { baseURL, viewport: { width: 1440, height: 960 }, serviceWorkers: 'block' },
  webServer: process.env.DASHBOARD_URL ? undefined : {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4185 --strictPort',
    url: baseURL,
    timeout: 120000,
  },
})
