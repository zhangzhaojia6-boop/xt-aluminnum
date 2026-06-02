import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSource = readFileSync(new URL('../src/config/navigation.js', import.meta.url), 'utf8')
const manageNavSource = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')
const settingsDrawerSource = readFileSync(new URL('../src/config/manage-settings-drawer.js', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('template center page is retired from frontend routes and navigation', () => {
  assert.equal(existsSync(new URL('../src/views/master/WorkshopTemplateConfig.vue', import.meta.url)), false)
  assert.doesNotMatch(routerSource, /WorkshopTemplateConfig/)
  assert.doesNotMatch(routerSource, /name:\s*'admin-template-center'/)
  assert.doesNotMatch(navSource, /admin-template-center/)
  assert.doesNotMatch(manageNavSource, /\/manage\/admin\/templates/)
  assert.doesNotMatch(settingsDrawerSource, /\/manage\/admin\/templates/)
})

test('frontend no longer exposes template center api helpers', () => {
  assert.doesNotMatch(masterApiSource, /fetchWorkshopTemplateConfig/)
  assert.doesNotMatch(masterApiSource, /updateWorkshopTemplateConfig/)
  assert.doesNotMatch(masterApiSource, /\/master\/workshop-templates/)
})
