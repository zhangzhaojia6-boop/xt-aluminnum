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

async function scanWithBarcodeDetector() {
  throw new Error('browser_scanner_unavailable')
}

export function useScanLookup() {
  const scanning = ref(false)
  const canScan = computed(() => Boolean(dingtalkScanner()))

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
