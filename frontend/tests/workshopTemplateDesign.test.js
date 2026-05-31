import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/master/WorkshopTemplateConfig.vue', import.meta.url), 'utf8')
const masterApiSource = readFileSync(new URL('../src/api/master.js', import.meta.url), 'utf8')

test('WorkshopTemplateConfig keeps the real template editor contract', () => {
  assert.match(source, /data-testid="template-editor-page"/)
  assert.match(source, /data-testid="template-workshop-select"/)
  assert.match(source, /data-testid="template-save"/)
  assert.match(source, /fetchWorkshops\(\{\s*limit:\s*500\s*\}\)/)
  assert.match(source, /fetchWorkshopTemplateConfig/)
  assert.match(source, /updateWorkshopTemplateConfig/)
  assert.match(source, /updateWorkshopTemplateConfig\(selectedTemplateKey\.value,\s*payload\)/)
  assert.match(source, /entry_fields/)
  assert.match(source, /shift_fields/)
  assert.match(source, /extra_fields/)
  assert.match(source, /qc_fields/)
  assert.match(source, /readonly_fields/)
  assert.match(source, /:disabled="section\.key !== 'readonly_fields'"/)
  assert.match(source, /:data-testid="`template-section-\$\{section\.key\}`"/)
  assert.match(source, /:data-testid="`template-add-\$\{section\.key\}`"/)
})

test('WorkshopTemplateConfig applies the industrial blue matrix surface', () => {
  assert.match(source, /class="page-stack template-center"/)
  assert.match(source, /template-center__hero/)
  assert.match(source, /FIELD TEMPLATE MATRIX/)
  assert.match(source, /id="template-center-title">模板中心/)
  assert.match(source, /template-center__overview/)
  assert.match(source, /template-center__section/)
  assert.match(source, /templateStats/)
  assert.match(source, /--template-accent:\s*#00f2ff/)
  assert.match(source, /templateScanline/)
  assert.match(source, /@media \(max-width: 640px\)/)
  assert.doesNotMatch(source, /ReferencePageFrame/)
  assert.doesNotMatch(source, /title="主数据与模板中心"/)
})

test('master api still points template reads and writes at backend template endpoints', () => {
  assert.match(masterApiSource, /\/master\/workshop-templates\/\$\{templateKey\}/)
  assert.match(masterApiSource, /fetchWorkshopTemplateConfig/)
  assert.match(masterApiSource, /updateWorkshopTemplateConfig/)
})
