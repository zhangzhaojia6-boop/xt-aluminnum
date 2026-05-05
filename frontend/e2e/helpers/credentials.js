import { test } from '@playwright/test'

export function firstEnv(...names) {
  for (const name of names) {
    const value = process.env[name]
    if (value) return value
  }
  return ''
}

export function skipWithoutCredentials(requirements) {
  const missing = requirements
    .filter(([, value]) => !value)
    .map(([name]) => name)

  test.skip(
    missing.length > 0,
    `Set ${missing.join(', ')} to run this credentialed E2E test`
  )
}
