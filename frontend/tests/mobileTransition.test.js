import test from 'node:test'
import assert from 'node:assert/strict'

import { buildMobileTransitionMapping, resolveTransitionRoleBucket } from '../src/utils/mobileTransition.js'

test('owner daily roles keep owner entry even when bound to a QR machine', () => {
  assert.equal(resolveTransitionRoleBucket({ role: 'consumable_stat', isMachineBound: true }), 'consumable_stat')
  assert.equal(resolveTransitionRoleBucket({ role: 'quality_owner', isMachineBound: true }), 'quality_owner')

  const mapping = buildMobileTransitionMapping({
    role: 'consumable_stat',
    isMachineBound: true,
    reportStatus: 'unreported',
  })

  assert.equal(mapping.role_bucket, 'consumable_stat')
  assert.equal(mapping.primary_cta, '填生产内勤')
})

test('shift auxiliary energy role keeps energy entry even when QR-bound', () => {
  assert.equal(resolveTransitionRoleBucket({ role: 'energy_stat', isMachineBound: true }), 'energy_stat')

  const mapping = buildMobileTransitionMapping({
    role: 'energy_stat',
    isMachineBound: true,
    reportStatus: 'unreported',
  })

  assert.equal(mapping.role_bucket, 'energy_stat')
  assert.equal(mapping.primary_cta, '填能耗')
})

test('machine-bound operator roles still use production entry', () => {
  assert.equal(resolveTransitionRoleBucket({ role: 'machine_operator', isMachineBound: true }), 'machine_operator')
  assert.equal(resolveTransitionRoleBucket({ role: 'mobile_user', isMachineBound: true }), 'machine_operator')
})
