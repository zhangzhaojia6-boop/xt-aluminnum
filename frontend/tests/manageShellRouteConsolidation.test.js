import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSource = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')

test('energy is mounted inside the manage shell; the attendance placeholder is retired', () => {
  assert.match(routerSource, /path:\s*'energy',\s*name:\s*'energy-center',\s*component:\s*EnergyCenter/)
  assert.match(routerSource, /path:\s*'attendance',\s*name:\s*'attendance-overview',\s*redirect:\s*\{\s*name:\s*'manage-today'\s*\}/)
  assert.match(navSource, /path:\s*'\/manage\/energy'/)
  assert.doesNotMatch(navSource, /'\/manage\/attendance'/)
})

test('legacy energy and attendance links redirect into manage shell', () => {
  assert.match(routerSource, /path:\s*'\/energy\/center',\s*redirect:\s*preserveRouteState\('\/manage\/energy'\)/)
  assert.match(routerSource, /path:\s*'\/attendance\/overview',\s*redirect:\s*preserveRouteState\('\/manage\/attendance'\)/)
})
