import { request } from '@playwright/test'

import fs from 'node:fs'
import path from 'node:path'

import { shouldIgnoreHttpsErrors } from './helpers/tls.js'

const AUTH_FILE = path.resolve('e2e/.auth/user.json')
const FRONTEND_ORIGIN = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173'
const BACKEND_URL = process.env.PLAYWRIGHT_BACKEND_URL || 'http://localhost:8000'
const USERNAME = process.env.PLAYWRIGHT_USERNAME || process.env.INIT_ADMIN_USERNAME || 'admin'
const PASSWORD = process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'E2eAdmin#2026'

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

async function loginWithRetry() {
  let lastError

  for (let attempt = 1; attempt <= 30; attempt += 1) {
    const ctx = await request.newContext({
      baseURL: BACKEND_URL,
      ignoreHTTPSErrors: shouldIgnoreHttpsErrors({ baseURL: BACKEND_URL })
    })
    try {
      const response = await ctx.post('/api/v1/auth/login', {
        data: { username: USERNAME, password: PASSWORD }
      })

      if (response.ok()) {
        return await response.json()
      }

      lastError = new Error(`login returned ${response.status()}: ${await response.text()}`)
      if (response.status() === 429) {
        const retryAfter = Number(response.headers()['retry-after'] || 1)
        await sleep(Math.max(1, Math.min(60, retryAfter)) * 1000)
        continue
      }
    } catch (error) {
      lastError = error
    } finally {
      await ctx.dispose()
    }

    await sleep(1000)
  }

  throw lastError
}

export default async function globalSetup() {
  const auth = await loginWithRetry()
  const origin = new URL(FRONTEND_ORIGIN).origin
  const user = auth.user || null
  const machine = auth.machine_info || null

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  fs.writeFileSync(
    AUTH_FILE,
    JSON.stringify({
      cookies: [],
      origins: [{
        origin,
        localStorage: [
          { name: 'xt_access_token', value: auth.access_token },
          { name: 'xt_refresh_token', value: auth.refresh_token },
          { name: 'aluminum_bypass_token', value: auth.access_token },
          { name: 'aluminum_bypass_user', value: JSON.stringify(user) },
          { name: 'aluminum_bypass_machine', value: machine ? JSON.stringify(machine) : '' }
        ]
      }]
    }, null, 2)
  )
}
