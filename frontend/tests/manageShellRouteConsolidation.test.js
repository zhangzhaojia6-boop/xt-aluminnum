import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSource = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')

test('energy and attendance are mounted inside the manage shell', () => {
  assert.match(routerSource, /path:\s*'energy',\s*name:\s*'energy-center',\s*component:\s*EnergyCenter/)
  assert.match(routerSource, /path:\s*'attendance',\s*name:\s*'attendance-overview',\s*component:\s*AttendanceOverview/)
  assert.match(navSource, /path:\s*'\/manage\/energy'/)
  assert.match(navSource, /path:\s*'\/manage\/attendance'/)
})

test('legacy energy and attendance links redirect into manage shell', () => {
  assert.match(routerSource, /path:\s*'\/energy\/center',\s*redirect:\s*preserveRouteState\('\/manage\/energy'\)/)
  assert.match(routerSource, /path:\s*'\/attendance\/overview',\s*redirect:\s*preserveRouteState\('\/manage\/attendance'\)/)
})
