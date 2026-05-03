import { computed, ref } from 'vue'

import { fetchScanLookup } from '../api/mobile.js'

function dingtalkScanner() {
  const dd = globalThis.window?.dd
  return dd && dd.biz && dd.biz.util && dd.biz.util.scan ? dd.biz.util.scan : null
}

function hasBrowserDetector() {
  return typeof globalThis.window !== 'undefined' && 'BarcodeDetector' in globalThis.window
}

function parseDingtalkScanResult(result) {
  return String(result?.text || result?.result || result?.qrCode || result?.code || '').trim()
}

function scanWithDingtalk() {
  const scan = dingtalkScanner()
  if (!scan) return Promise.reject(new Error('scanner_unavailable'))
  return new Promise((resolve, reject) => {
    scan({
      type: 'qrCode',
      onSuccess(result) {
        const value = parseDingtalkScanResult(result)
        if (value) resolve(value)
        else reject(new Error('scan_empty'))
      },
      onFail(error) {
        reject(error || new Error('scan_failed'))
      }
    })
  })
}

function detectedCodeValue(codes) {
  const first = Array.isArray(codes) ? codes.find(code => code?.rawValue || code?.rawData) : null
  return String(first?.rawValue || first?.rawData || '').trim()
}

function waitForNextScanFrame() {
  return new Promise(resolve => setTimeout(resolve, 250))
}

async function scanWithBarcodeDetector() {
  if (!hasBrowserDetector()) throw new Error('scanner_unavailable')
  const mediaDevices = globalThis.navigator?.mediaDevices
  const documentRef = globalThis.document
  if (!mediaDevices?.getUserMedia || !documentRef?.createElement) throw new Error('scanner_unavailable')

  const stream = await mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
  const video = documentRef.createElement('video')
  video.muted = true
  video.playsInline = true
  video.srcObject = stream
  await video.play()

  const detector = new globalThis.window.BarcodeDetector({ formats: ['qr_code'] })
  const startedAt = Date.now()
  try {
    while (Date.now() - startedAt < 15000) {
      const value = detectedCodeValue(await detector.detect(video))
      if (value) return value
      await waitForNextScanFrame()
    }
    throw new Error('scan_timeout')
  } finally {
    stream.getTracks().forEach(track => track.stop())
    video.srcObject = null
  }
}

export function useScanLookup() {
  const scanning = ref(false)
  const canScan = computed(() => Boolean(dingtalkScanner()) || hasBrowserDetector())

  async function scanLookup(qr) {
    const value = qr || (dingtalkScanner() ? await scanWithDingtalk() : await scanWithBarcodeDetector())
    return fetchScanLookup(value)
  }

  async function scan() {
    if (scanning.value) return null
    scanning.value = true
    try {
      return await scanLookup()
    } finally {
      scanning.value = false
    }
  }

  return {
    canScan,
    scanning,
    scan,
    scanLookup
  }
}
