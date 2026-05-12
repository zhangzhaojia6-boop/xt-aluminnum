import { test } from 'node:test'
import assert from 'node:assert/strict'
import { registerHudEchartsTheme, XT_HUD_THEME_NAME } from '../src/design/echarts-hud.js'

test('XT_HUD_THEME_NAME is "xt-hud"', () => {
  assert.equal(XT_HUD_THEME_NAME, 'xt-hud')
})

test('registerHudEchartsTheme registers under xt-hud with a multi-color palette', () => {
  const calls = []
  const fakeEcharts = { registerTheme: (name, theme) => calls.push({ name, theme }) }
  registerHudEchartsTheme(fakeEcharts)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].name, 'xt-hud')
  assert.ok(Array.isArray(calls[0].theme.color) && calls[0].theme.color.length >= 4)
  const bg = calls[0].theme.backgroundColor
  assert.ok(bg === 'transparent' || bg.toLowerCase().startsWith('#0') || bg.startsWith('rgba'))
})

test('registerHudEchartsTheme is idempotent enough to run twice', () => {
  const calls = []
  const fakeEcharts = { registerTheme: (name) => calls.push(name) }
  registerHudEchartsTheme(fakeEcharts)
  registerHudEchartsTheme(fakeEcharts)
  assert.deepEqual(calls, ['xt-hud', 'xt-hud'])
})
