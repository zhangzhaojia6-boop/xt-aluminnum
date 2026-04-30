<template>
  <div class="qr-print-page">
    <div class="qr-print-header">
      <h1>机台与车间 QR 码</h1>
      <el-button type="primary" @click="handlePrint">打印全部</el-button>
    </div>

    <div v-if="loading" class="qr-print-loading">加载中…</div>

    <div v-for="group in groupedEquipment" :key="group.workshopName" class="qr-print-group">
      <h2>{{ group.workshopName }}</h2>
      <div class="qr-print-grid">
        <div v-for="eq in group.items" :key="eq.id" class="qr-print-card">
          <img v-if="qrImages[eq.qr_code]" :src="qrImages[eq.qr_code]" :alt="eq.qr_code" class="qr-print-card__img" />
          <strong>{{ eq.name }}</strong>
          <code>{{ eq.qr_code }}</code>
          <span class="qr-print-card__url">{{ buildLoginUrl(eq) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import QRCode from 'qrcode'
import { computed, onMounted, ref } from 'vue'

import { fetchEquipment, fetchWorkshops } from '../../api/master.js'

const loading = ref(true)
const equipmentList = ref([])
const workshopMap = ref({})
const qrImages = ref({})

const baseUrl = `${window.location.origin}`

const groupedEquipment = computed(() => {
  const groups = {}
  for (const eq of equipmentList.value) {
    if (!eq.qr_code) continue
    const wsName = workshopMap.value[eq.workshop_id] || '未知车间'
    if (!groups[wsName]) groups[wsName] = { workshopName: wsName, items: [] }
    groups[wsName].items.push(eq)
  }
  return Object.values(groups)
})

function buildLoginUrl(eq) {
  if (eq.equipment_type === 'virtual_workshop_qr') {
    const wsCode = eq.qr_code.replace('XT-', '').replace('-WS', '')
    return `${baseUrl}/login?workshop=${wsCode}`
  }
  return `${baseUrl}/login?machine=${eq.qr_code}`
}

async function generateQrImages() {
  for (const eq of equipmentList.value) {
    if (!eq.qr_code) continue
    const url = buildLoginUrl(eq)
    try {
      qrImages.value[eq.qr_code] = await QRCode.toDataURL(url, { width: 200, margin: 1 })
    } catch { /* skip */ }
  }
}

async function load() {
  loading.value = true
  try {
    const [eqData, wsData] = await Promise.all([fetchEquipment(), fetchWorkshops()])
    equipmentList.value = eqData || []
    const map = {}
    for (const ws of (wsData || [])) {
      map[ws.id] = ws.name
    }
    workshopMap.value = map
    await generateQrImages()
  } finally {
    loading.value = false
  }
}

function handlePrint() {
  window.print()
}

onMounted(load)
</script>

<style scoped>
.qr-print-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--xt-space-6);
}

.qr-print-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--xt-space-6);
}

.qr-print-header h1 {
  font-size: var(--xt-text-2xl);
  font-weight: 900;
}

.qr-print-loading {
  padding: var(--xt-space-8);
  text-align: center;
  color: var(--xt-text-muted);
}

.qr-print-group {
  margin-bottom: var(--xt-space-6);
}

.qr-print-group h2 {
  font-size: var(--xt-text-lg);
  font-weight: 700;
  margin-bottom: var(--xt-space-3);
  padding-bottom: var(--xt-space-2);
  border-bottom: 1px solid var(--xt-border-light);
}

.qr-print-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--xt-space-4);
}

.qr-print-card {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-4);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  text-align: center;
}

.qr-print-card__img {
  width: 160px;
  height: 160px;
  margin: 0 auto;
}

.qr-print-card strong {
  font-size: var(--xt-text-lg);
}

.qr-print-card code {
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
}

.qr-print-card__url {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
  word-break: break-all;
}

@media print {
  .qr-print-header .el-button {
    display: none;
  }

  .qr-print-card {
    break-inside: avoid;
    border: 1px solid #ccc;
  }
}
</style>
