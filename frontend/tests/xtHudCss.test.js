import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const file = path.resolve('src/design/xt-hud.css')

test('xt-hud.css exists', () => {
  assert.ok(fs.existsSync(file), 'src/design/xt-hud.css must exist')
})

test('xt-hud.css only targets [data-xt-theme="hud"] scope', () => {
  const src = fs.readFileSync(file, 'utf8')
  const stripped = src.replace(/\/\*[\s\S]*?\*\//g, '')
  const ruleBlocks = []
  let buf = ''
  let depth = 0
  for (const ch of stripped) {
    if (ch === '{') {
      if (depth === 0) {
        ruleBlocks.push(buf)
        buf = ''
      }
      depth += 1
    } else if (ch === '}') {
      depth -= 1
      buf = ''
    } else if (depth === 0) {
      buf += ch
    }
  }
  for (const selectorList of ruleBlocks) {
    for (const raw of selectorList.split(',')) {
      const sel = raw.trim()
      if (!sel || sel.startsWith('@')) continue
      assert.match(
        sel,
        /^(:root\[data-xt-theme="hud"\]|\[data-xt-theme="hud"\])/,
        `selector out of scope: ${sel}`
      )
    }
  }
})

test('xt-hud.css contains no !important', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.equal(src.includes('!important'), false, 'HUD CSS must not use !important')
})

test('xt-hud.css redefines the core tokens with the approved dark palette', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(src, /letter-spacing:\s*-/)
  for (const [token, value] of [
    ['--xt-bg-page', '#060d18'],
    ['--xt-bg-panel', '#0c1626'],
    ['--xt-bg-panel-strong', '#111e33'],
    ['--xt-border', '#1e2c44'],
    ['--xt-border-strong', '#2c3f5e'],
    ['--xt-text', '#e6edf7'],
    ['--xt-text-secondary', '#9aa8bd'],
    ['--xt-primary', '#4d8eff'],
    ['--xt-success', '#3ecf8e'],
    ['--xt-warning', '#f5b544'],
    ['--xt-danger', '#ff6b6b']
  ]) {
    assert.ok(src.includes(`${token}: ${value};`), token)
  }
  assert.doesNotMatch(src, /#5eb8ff/)
})

test('primary buttons use the darker solid blue with white text for contrast', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /--xt-primary-solid:\s*#1f5fd1;/)
  assert.match(src, /\.el-button--primary \{[^}]*--el-button-bg-color: var\(--xt-primary-solid\);[^}]*--el-button-text-color: #ffffff;/)
})

test('Element Plus variables are mapped to the same palette', () => {
  const src = fs.readFileSync(file, 'utf8')
  for (const token of ['--el-bg-color:', '--el-bg-color-overlay:', '--el-text-color-primary:', '--el-border-color:', '--el-fill-color-blank:', '--el-color-primary:']) {
    assert.ok(src.includes(token), token)
  }
})

test('printing always restores white paper and dark text', () => {
  const src = fs.readFileSync(file, 'utf8')
  const print = src.slice(src.indexOf('@media print'))
  assert.match(print, /--xt-bg-page: #ffffff;/)
  assert.match(print, /--xt-text: #111827;/)
  assert.match(print, /color-scheme: light;/)
})

test('xt-hud.css has no forbidden product lexicon', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})
