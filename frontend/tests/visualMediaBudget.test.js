import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'

const mediaDir = new URL('../public/media/', import.meta.url)
const images = readdirSync(mediaDir).filter((name) => name !== 'CREDITS.md')

test('media images are WebP within the size budget and all credited', () => {
  const credits = readFileSync(new URL('CREDITS.md', mediaDir), 'utf8')
  let total = 0
  assert.ok(images.length > 0)
  for (const name of images) {
    assert.match(name, /\.webp$/, name)
    const size = statSync(new URL(name, mediaDir)).size
    assert.ok(size <= 150_000, `${name} ${size}`)
    assert.ok(credits.includes(name), `${name} missing from CREDITS.md`)
    total += size
  }
  assert.ok(total <= 1_500_000, `total ${total}`)
})

test('runtime image cache covers webp and is bounded', () => {
  const config = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8')
  assert.match(config, /gif\|webp\)\$\//)
  assert.match(config, /maxEntries: 60/)
  assert.match(config, /maxAgeSeconds: 30 \* 24 \* 60 \* 60/)
})

test('login photo loads only on wide screens and respects reduced motion', () => {
  const login = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
  assert.match(login, /@media \(min-width: 861px\) \{\s*\.login-stage__photo \{[^}]*url\('\/media\/login-coils\.webp'\)/)
  assert.doesNotMatch(login, /<img[^>]*login-coils/)
  assert.match(login, /prefers-reduced-motion: reduce\) \{\s*\.login-stage__photo \{\s*animation: none/)
})
