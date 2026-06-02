import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildRealtimeStreamRequest, parseSseChunk } from '../src/composables/useRealtimeStream.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('buildRealtimeStreamRequest keeps token out of the URL and uses Authorization header', () => {
  global.window = {
    location: { origin: 'http://localhost:8080' }
  }

  const request = buildRealtimeStreamRequest({
    pathname: '/realtime/stream',
    scope: 'all',
    token: 'jwt-token',
    lastEventId: '12',
    apiBase: '/api/v1'
  })

  assert.equal(request.url, 'http://localhost:8080/api/v1/realtime/stream?scope=all&last_event_id=12')
  assert.equal(request.headers.Authorization, 'Bearer jwt-token')
  assert.equal(request.url.includes('token='), false)
})

test('parseSseChunk emits complete events and keeps partial frames buffered', () => {
  const firstPass = parseSseChunk('', 'id: 7\nevent: entry_submitted\ndata: {"tracking_card_no":"RA260001"}\n\nid: 8\nevent')

  assert.equal(firstPass.events.length, 1)
  assert.deepEqual(firstPass.events[0], {
    id: '7',
    type: 'entry_submitted',
    data: '{"tracking_card_no":"RA260001"}'
  })
  assert.equal(firstPass.buffer, 'id: 8\nevent')

  const secondPass = parseSseChunk(firstPass.buffer, ': heartbeat\n\nid: 8\nevent: entry_verified\ndata: {"tracking_card_no":"RA260001"}\n\n')

  assert.equal(secondPass.events.length, 1)
  assert.deepEqual(secondPass.events[0], {
    id: '8',
    type: 'entry_verified',
    data: '{"tracking_card_no":"RA260001"}'
  })
  assert.equal(secondPass.buffer, '')
})

test('useRealtimeStream aborts a stuck connecting stream so the page can fall back', () => {
  const src = source('../src/composables/useRealtimeStream.js')

  assert.match(src, /connectionTimeoutMs/)
  assert.match(src, /status\.value === 'connecting'/)
  assert.match(src, /controller\.abort\(\)/)
})

test('LiveDashboardPage polls snapshots when the realtime stream is not open', () => {
  const src = source('../src/views/manage/live/LiveDashboardPage.vue')

  assert.match(src, /SNAPSHOT_POLL_MS/)
  assert.match(src, /streamStatus\.value !== 'open'/)
  assert.match(src, /快照刷新中/)
})
