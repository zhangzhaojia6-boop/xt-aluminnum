import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const routerSrc = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const srcRoot = fileURLToPath(new URL('../src', import.meta.url))

function activeSourceFiles(dir) {
  const files = []
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      files.push(...activeSourceFiles(path))
    } else if (/\.(js|vue)$/.test(entry)) {
      files.push(path)
    }
  }
  return files
}

test('retired import routes redirect to system settings', () => {
  const redirectPatterns = [
    /path:\s*['"]ingestion['"],\s*name:\s*['"]admin-ingestion-center['"],\s*redirect:\s*\{\s*name:\s*['"]admin-ops-reliability['"]\s*\}/,
    /path:\s*['"]imports['"],\s*name:\s*['"]manage-imports['"],\s*redirect:\s*\{\s*name:\s*['"]admin-ops-reliability['"]\s*\}/,
    /path:\s*['"]\/review\/ingestion['"],\s*name:\s*['"]review-ingestion-center['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/admin\/settings['"]\)/,
    /path:\s*['"]\/imports\/files['"],\s*name:\s*['"]file-import['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/admin\/settings['"]\)/,
    /path:\s*['"]\/imports\/history['"],\s*redirect:\s*['"]\/manage\/admin\/settings['"]/,
  ]

  for (const pattern of redirectPatterns) {
    assert.match(routerSrc, pattern)
  }
})

test('retired import frontend pages and api wrapper are removed', () => {
  const retiredFiles = [
    '../src/api/imports.js',
    '../src/views/imports/ImportHistory.vue',
    '../src/views/review/IngestionCenter.vue',
  ]

  for (const file of retiredFiles) {
    assert.equal(existsSync(new URL(file, import.meta.url)), false, `${file} should be removed`)
  }
})

test('active frontend source no longer imports retired import api helpers', () => {
  const activeSource = activeSourceFiles(srcRoot)
    .map((path) => readFileSync(path, 'utf8'))
    .join('\n')

  assert.equal(/api\/imports|fetchImportHistory|fetchDailyProductionMappingPreview|listImportBatches/.test(activeSource), false)
})
