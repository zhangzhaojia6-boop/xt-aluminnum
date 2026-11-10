import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { countHardCodedColors } from './helpers-color-count.js'

const srcRoot = fileURLToPath(new URL('../src', import.meta.url))
const baseline = JSON.parse(readFileSync(new URL('./fixtures/color-baseline.json', import.meta.url), 'utf8'))

// 暗色主题靠 token；写死颜色只许减少。清理后把基线同步改小，新文件基线为 0。
test('pages never add hard-coded colors beyond the baseline', () => {
  const current = countHardCodedColors(srcRoot)
  const grown = Object.entries(current)
    .filter(([file, n]) => n > (baseline[file] || 0))
    .map(([file, n]) => `${file}: ${baseline[file] || 0} -> ${n}`)
  assert.deepEqual(grown, [], `写死颜色增加了，请改用 --xt-* token：\n${grown.join('\n')}`)
})

test('the baseline is tight: it shrinks when a file gets cleaner', () => {
  const current = countHardCodedColors(srcRoot)
  const loose = Object.entries(baseline)
    .filter(([file, n]) => (current[file] || 0) < n)
    .map(([file, n]) => `${file}: ${n} -> ${current[file] || 0}`)
  assert.deepEqual(loose, [], `这些文件已经更干净，请把 tests/fixtures/color-baseline.json 同步改小：\n${loose.join('\n')}`)
})
