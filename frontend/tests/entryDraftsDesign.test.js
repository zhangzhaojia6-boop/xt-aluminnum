import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/entry/EntryDrafts.vue', import.meta.url), 'utf8')

test('EntryDrafts keeps local draft storage and restore route behavior', () => {
  assert.match(src, /Object\.keys\(localStorage\)\.filter\(\(key\) => key\.startsWith\('draft:'\)\)/)
  assert.match(src, /const businessDate = segments\[3\] \|\| ''/)
  assert.match(src, /const shiftId = segments\[2\] \|\| ''/)
  assert.match(src, /localStorage\.removeItem\(key\)/)
  assert.match(src, /name:\s*'mobile-unified-entry'/)
  assert.match(src, /businessDate:\s*item\.businessDate/)
  assert.match(src, /shiftId:\s*item\.shiftId/)
  assert.doesNotMatch(src, /from ['"].*api/)
})

test('EntryDrafts uses the industrial draft recovery visual system', () => {
  assert.match(src, /草稿恢复/)
  assert.match(src, /entry-drafts__hero/)
  assert.match(src, /entry-drafts__readout/)
  assert.match(src, /entry-drafts__status/)
  assert.match(src, /entry-drafts__empty-ring/)
  assert.match(src, /--draft-index/)
  assert.match(src, /@keyframes entryDraftScan/)
  assert.match(src, /@keyframes entryDraftCardIn/)
  assert.match(src, /@keyframes entryDraftLed/)
  assert.match(src, /#00f2ff/)
  assert.doesNotMatch(src, /purple|lavender|violet/i)
})
