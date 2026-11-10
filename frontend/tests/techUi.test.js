import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { RING_CIRCUMFERENCE, pulseState, ringArc } from '../src/utils/ring-arc.js'

test('ring draws only real ratios: none for missing, full for over 100%', () => {
  assert.equal(ringArc(null).hasArc, false)
  assert.equal(ringArc(undefined).hasArc, false)
  assert.equal(ringArc('').hasArc, false)
  assert.equal(ringArc('abc').hasArc, false)
  assert.equal(ringArc(-0.2).hasArc, false)
  assert.equal(ringArc(0).hasArc, true)
  assert.equal(ringArc(0.5).dash.split(' ')[0], (RING_CIRCUMFERENCE / 2).toFixed(2))
  assert.equal(ringArc(1.3).dash.split(' ')[0], RING_CIRCUMFERENCE.toFixed(2))
})

test('connection tone maps to pulse states', () => {
  assert.equal(pulseState('success'), 'live')
  assert.equal(pulseState('warning'), 'stale')
  assert.equal(pulseState('danger'), 'offline')
  assert.equal(pulseState(undefined), 'stale')
})

test('only the live pulse breathes and it stops for reduced motion', () => {
  const src = readFileSync(new URL('../src/components/xt/XtPulseDot.vue', import.meta.url), 'utf8')
  assert.match(src, /\.xt-pulse\.is-live \{[^}]*animation: xt-pulse-breathe 2s/)
  assert.match(src, /prefers-reduced-motion: reduce\) \{\s*\.xt-pulse\.is-live \{ animation: none; \}/)
})

test('tech frame corners are 12px fine lines in the strong border token', () => {
  const src = readFileSync(new URL('../src/components/xt/XtTechFrame.vue', import.meta.url), 'utf8')
  assert.match(src, /width: 12px; height: 12px; border: 0 solid var\(--xt-border-strong\)/)
})

test('overview puts the single tech frame around the main output chart', () => {
  const src = readFileSync(new URL('../src/views/manage/today/TodayPage.vue', import.meta.url), 'utf8')
  assert.equal((src.match(/<XtTechFrame/g) || []).length, 1)
  assert.match(src, /<XtRing :ratio="item\.value == null \? null : Number\(item\.value\) \/ 100"/)
})
