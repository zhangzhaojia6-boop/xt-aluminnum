import test from 'node:test'
import assert from 'node:assert/strict'

import { checkMachineMismatch, warnIfMachineMismatch } from '../src/composables/useMachineMismatch.js'

const matchingResult = {
  source: 'coil_snapshot',
  machine_line_id: 7,
  machine_line_code: 'LZ2050-1',
  machine_line_name: '2050冷轧机',
  machine_binding_source: 'route_inferred',
}

const conflictingResult = {
  source: 'coil_snapshot',
  machine_line_id: 9,
  machine_line_code: 'LZ2050-2',
  machine_line_name: '2050冷轧机2号',
  machine_binding_source: 'route_inferred',
}

const unresolvedResult = {
  source: 'coil_snapshot',
  machine_line_id: null,
  machine_line_code: null,
  machine_line_name: null,
  machine_binding_source: 'unresolved',
}

const machineIdentityResult = {
  source: 'machine_identity',
  header_fields: {},
}

function makeAuth(machineId, name = '2050冷轧机') {
  return {
    boundMachineId: machineId,
    machineContext: machineId == null ? null : {
      machine_id: machineId,
      machine_name: name,
      machine_code: name,
    },
  }
}

test('checkMachineMismatch returns null when bound and inferred match', () => {
  assert.equal(checkMachineMismatch(matchingResult, makeAuth(7)), null)
})

test('checkMachineMismatch returns mismatch detail when bound differs from inferred', () => {
  const m = checkMachineMismatch(conflictingResult, makeAuth(7, '2050冷轧机'))
  assert.equal(m.boundId, 7)
  assert.equal(m.inferredId, 9)
  assert.equal(m.inferredName, '2050冷轧机2号')
  assert.equal(m.boundName, '2050冷轧机')
})

test('checkMachineMismatch returns null when scan binding source is unresolved', () => {
  assert.equal(checkMachineMismatch(unresolvedResult, makeAuth(7)), null)
})

test('checkMachineMismatch returns null for machine_identity scans (machine code QR)', () => {
  assert.equal(checkMachineMismatch(machineIdentityResult, makeAuth(7)), null)
})

test('checkMachineMismatch returns null when user has no bound machine', () => {
  assert.equal(checkMachineMismatch(conflictingResult, makeAuth(null)), null)
})

test('warnIfMachineMismatch invokes ElMessage.warning only on mismatch', () => {
  const calls = []
  const fakeMessage = { warning: (payload) => calls.push(payload) }

  warnIfMachineMismatch(matchingResult, makeAuth(7), fakeMessage)
  assert.equal(calls.length, 0, 'matching pair must not trigger warning')

  warnIfMachineMismatch(conflictingResult, makeAuth(7, '2050冷轧机'), fakeMessage)
  assert.equal(calls.length, 1, 'mismatch must trigger exactly one warning')
  assert.match(calls[0].message, /2050冷轧机/)
  assert.match(calls[0].message, /2050冷轧机2号/)
})
