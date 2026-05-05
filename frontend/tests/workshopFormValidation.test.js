import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  hasWorkshopIdentity,
  normalizeWorkshopPayload,
} from '../src/utils/workshopFormValidation.js'

const workshopPageSource = readFileSync(
  new URL('../src/views/master/Workshop.vue', import.meta.url),
  'utf8',
)

test('hasWorkshopIdentity rejects blank workshop code or name', () => {
  assert.equal(hasWorkshopIdentity({ code: '', name: '铸轧二车间' }), false)
  assert.equal(hasWorkshopIdentity({ code: 'ZR2', name: '   ' }), false)
  assert.equal(hasWorkshopIdentity({ code: ' ZR2 ', name: ' 铸轧二车间 ' }), true)
})

test('normalizeWorkshopPayload trims identity fields and keeps other form fields', () => {
  assert.deepEqual(
    normalizeWorkshopPayload({
      code: ' ZR2 ',
      name: ' 铸轧二车间 ',
      sort_order: 2,
      is_active: true,
    }),
    {
      code: 'ZR2',
      name: '铸轧二车间',
      sort_order: 2,
      is_active: true,
    },
  )
})

test('Workshop dialog wires required validation before save', () => {
  assert.match(workshopPageSource, /:rules="workshopRules"/)
  assert.match(workshopPageSource, /prop="code"/)
  assert.match(workshopPageSource, /prop="name"/)
  assert.match(workshopPageSource, /formRef\.value\.validate\(\)/)
  assert.match(workshopPageSource, /normalizeWorkshopPayload\(form\)/)
})

test('Workshop page labels the runtime surface as workshop master data', () => {
  assert.match(workshopPageSource, /title="车间主数据"/)
  assert.match(workshopPageSource, /:tags="\['车间清单', '新增编辑删除', '主数据治理'\]"/)
  assert.doesNotMatch(workshopPageSource, /title="主数据与模板中心"/)
  assert.doesNotMatch(workshopPageSource, /班组员工/)
  assert.doesNotMatch(workshopPageSource, /机台班次/)
})
