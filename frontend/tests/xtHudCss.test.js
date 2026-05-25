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

test('xt-hud.css follows compact radius and letter-spacing rules', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(src, /letter-spacing:\s*-/)
  assert.match(src, /--xt-hud-radius-lg:\s*8px/)
  assert.doesNotMatch(src, /--xt-hud-radius-lg:\s*(1[0-9]|[2-9][0-9])px/)
})

test('xt-hud.css defines HUD tokens as CSS variables', () => {
  const src = fs.readFileSync(file, 'utf8')
  for (const v of ['--xt-hud-canvas', '--xt-hud-panel', '--xt-hud-border', '--xt-hud-text', '--xt-hud-primary']) {
    assert.match(src, new RegExp(v.replace(/[-]/g, '\\-')), `missing token ${v}`)
  }
})

test('xt-hud.css has no forbidden product lexicon', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})
