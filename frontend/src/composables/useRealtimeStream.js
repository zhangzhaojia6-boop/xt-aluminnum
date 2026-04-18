import { computed, onBeforeUnmount, ref, unref, watch } from 'vue'

import { apiBaseUrl } from '../api/index.js'
import { useAuthStore } from '../stores/auth.js'

function resolveStreamUrl(pathname, apiBase = apiBaseUrl) {
  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    return new URL(`${apiBase.replace(/\/$/, '')}${pathname}`)
  }
  return new URL(`${apiBase.replace(/\/$/, '')}${pathname}`, window.location.origin)
}

export function buildRealtimeStreamRequest({
  pathname = '/realtime/stream',
  scope = 'all',
  token,
  lastEventId = '',
  apiBase = apiBaseUrl,
  signal
}) {
  const url = resolveStreamUrl(pathname, apiBase)
  url.searchParams.set('scope', String(scope || 'all'))
  if (lastEventId) {
    url.searchParams.set('last_event_id', String(lastEventId))
  }

  return {
    url: url.toString(),
    headers: {
      Accept: 'text/event-stream',
      Authorization: `Bearer ${token}`
    },
    signal
  }
}

function parseSseFrame(frame) {
  const lines = frame.split('\n')
  let type = 'message'
  let id = ''
  const dataLines = []

  for (const rawLine of lines) {
    if (!rawLine || rawLine.startsWith(':')) continue
    const separatorIndex = rawLine.indexOf(':')
    const field = separatorIndex >= 0 ? rawLine.slice(0, separatorIndex) : rawLine
    let value = separatorIndex >= 0 ? rawLine.slice(separatorIndex + 1) : ''
    if (value.startsWith(' ')) {
      value = value.slice(1)
    }

    if (field === 'event') {
      type = value || 'message'
    } else if (field === 'id') {
      id = value
    } else if (field === 'data') {
      dataLines.push(value)
    }
  }

  if (!dataLines.length) {
    return null
  }

  return {
    id,
    type,
    data: dataLines.join('\n')
  }
}

export function parseSseChunk(buffer, chunk) {
  const normalized = `${buffer || ''}${chunk || ''}`.replace(/\r\n?/g, '\n')
  const frames = normalized.split('\n\n')
  const nextBuffer = frames.pop() || ''
  const events = frames.map(parseSseFrame).filter(Boolean)
  return { buffer: nextBuffer, events }
}

export function useRealtimeStream(scopeSource, options = {}) {
  const authStore = useAuthStore()
  const status = ref('idle')
  const lastEventAt = ref('')
  const reconnectCount = ref(0)

  let abortController = null
  let reconnectTimer = null
  let reconnectDelay = 1000
  let lastEventId = ''
  let disposed = false

  const enabled = computed(() => options.enabled !== false)

  function clearReconnectTimer() {
    if (!reconnectTimer) return
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  function cleanupStream() {
    if (!abortController) return
    abortController.abort()
    abortController = null
  }

  function scheduleReconnect() {
    if (disposed || reconnectTimer) return
    status.value = 'reconnecting'
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      reconnectCount.value += 1
      void connect()
    }, reconnectDelay)
    reconnectDelay = Math.min(reconnectDelay * 2, 10000) + Math.random() * 1000
  }

  function handleParsedEvent(event) {
    if (event.id) {
      lastEventId = event.id
    }
    lastEventAt.value = new Date().toISOString()
    if (typeof options.onEvent !== 'function') return

    try {
      options.onEvent(event.type, JSON.parse(event.data), {
        eventId: lastEventId
      })
    } catch (error) {
      if (typeof options.onError === 'function') {
        options.onError(error)
      }
    }
  }

  async function connect() {
    clearReconnectTimer()
    cleanupStream()

    if (disposed || !enabled.value || !authStore.token) {
      status.value = 'idle'
      return
    }

    const controller = new AbortController()
    abortController = controller
    const request = buildRealtimeStreamRequest({
      pathname: '/realtime/stream',
      scope: String(unref(scopeSource) || 'all'),
      token: authStore.token,
      lastEventId,
      signal: controller.signal
    })

    status.value = 'connecting'

    try {
      const response = await fetch(request.url, {
        headers: request.headers,
        signal: request.signal
      })

      if (abortController !== controller || disposed) {
        return
      }
      if (!response.ok) {
        throw new Error(`实时流连接失败（状态码 ${response.status}）`)
      }
      if (!response.body) {
        throw new Error('实时流不可用')
      }

      status.value = 'open'
      reconnectDelay = 1000

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (!disposed && abortController === controller) {
        const { value, done } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        const parsed = parseSseChunk(buffer, chunk)
        buffer = parsed.buffer
        parsed.events.forEach(handleParsedEvent)
      }

      if (!disposed && abortController === controller) {
        const finalChunk = decoder.decode()
        if (finalChunk) {
          const parsed = parseSseChunk(buffer, finalChunk)
          parsed.events.forEach(handleParsedEvent)
        }
      }
    } catch (error) {
      if (controller.signal.aborted || abortController !== controller || disposed) {
        return
      }
      if (typeof options.onError === 'function') {
        options.onError(error)
      }
    } finally {
      if (abortController === controller) {
        abortController = null
        if (!disposed && enabled.value && authStore.token) {
          scheduleReconnect()
        }
      }
    }
  }

  function disconnect() {
    clearReconnectTimer()
    cleanupStream()
    status.value = 'closed'
  }

  watch(
    [() => authStore.token, () => unref(scopeSource), enabled],
    () => {
      lastEventId = ''
      reconnectDelay = 1000
      if (enabled.value && authStore.token) {
        void connect()
      } else {
        disconnect()
      }
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    disposed = true
    disconnect()
  })

  return {
    status,
    lastEventAt,
    reconnectCount,
    connect,
    disconnect
  }
}
