import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: process.env.VISUAL_MATCH ? process.env.VISUAL_MATCH.split(',') : 'visual-*.spec.js',
  timeout: 45000,
  workers: 1,
  reporter: 'line',
  use: { ...devices['Desktop Edge'], channel: 'msedge', video: process.env.VISUAL_VIDEO ? { mode: 'on', size: { width: 1440, height: 900 } } : 'off', baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173' }
})
