<template>
  <section class="qr-print-page" data-testid="qr-print-page" aria-labelledby="qr-print-title">
    <header class="qr-print-hero">
      <div class="qr-print-hero__copy">
        <span>MACHINE QR MATRIX</span>
        <h1 id="qr-print-title">QR 打印中心</h1>
      </div>
      <div class="qr-print-hero__actions">
        <span class="qr-print-hero__signal" aria-hidden="true"></span>
        <el-button class="qr-print-hero__button" type="primary" :disabled="loading || !hasPrintableQr" @click="handlePrint">打印全部</el-button>
      </div>
    </header>

    <section class="qr-print-stats" aria-label="QR 打印状态">
      <article v-for="stat in qrSummary" :key="stat.label" class="qr-print-stat" :class="`is-${stat.tone}`">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </section>

    <section v-if="loading" class="qr-print-loading" aria-live="polite">
      <span></span>
      <strong>加载中…</strong>
    </section>

    <section v-else-if="!hasPrintableQr" class="qr-print-empty">
      <strong>暂无 QR 码</strong>
    </section>

    <section v-else class="qr-print-groups">
      <article v-for="group in groupedEquipment" :key="group.workshopName" class="qr-print-group">
        <div class="qr-print-group__head">
          <h2>{{ group.workshopName }}</h2>
          <span>{{ group.items.length }} 个</span>
        </div>
        <div class="qr-print-grid">
          <div v-for="eq in group.items" :key="eq.id" class="qr-print-card">
            <div class="qr-print-card__qr">
              <img v-if="qrImages[eq.qr_code]" :src="qrImages[eq.qr_code]" :alt="eq.qr_code" class="qr-print-card__img" />
            </div>
            <strong>{{ eq.name }}</strong>
            <code>{{ eq.qr_code }}</code>
            <span class="qr-print-card__url">{{ buildLoginUrl(eq) }}</span>
          </div>
        </div>
      </article>
    </section>
  </section>
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

const printableEquipment = computed(() => equipmentList.value.filter((eq) => eq.qr_code))

const groupedEquipment = computed(() => {
  const groups = {}
  for (const eq of printableEquipment.value) {
    const wsName = workshopMap.value[eq.workshop_id] || '未知车间'
    if (!groups[wsName]) groups[wsName] = { workshopName: wsName, items: [] }
    groups[wsName].items.push(eq)
  }
  return Object.values(groups)
})

const hasPrintableQr = computed(() => printableEquipment.value.length > 0)
const qrSummary = computed(() => {
  const workshopQrCount = printableEquipment.value.filter((eq) => eq.equipment_type === 'virtual_workshop_qr').length
  const directorQrCount = printableEquipment.value.filter(isDirectorQr).length
  const machineQrCount = printableEquipment.value.length - workshopQrCount - directorQrCount
  return [
    { label: '可打印二维码', value: printableEquipment.value.length, tone: 'primary' },
    { label: '车间分组', value: groupedEquipment.value.length, tone: 'success' },
    { label: '机台二维码', value: machineQrCount, tone: 'info' },
    { label: '主任看板码', value: directorQrCount, tone: 'success' },
    { label: '车间二维码', value: workshopQrCount, tone: 'warning' }
  ]
})

function isDirectorQr(eq) {
  return eq.equipment_type === 'virtual_role_qr' && String(eq.code || '').toUpperCase().endsWith('-DIR')
}

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
  position: relative;
  isolation: isolate;
  display: grid;
  gap: 16px;
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--xt-space-6);
  color: rgba(225, 253, 255, 0.94);
  --qr-accent: #00f2ff;
  --qr-line: rgba(0, 242, 255, 0.16);
  --qr-line-strong: rgba(0, 242, 255, 0.38);
  --qr-panel: rgba(6, 29, 51, 0.88);
  --qr-muted: rgba(185, 223, 235, 0.66);
}

.qr-print-page::before {
  position: absolute;
  inset: -22px 0 auto;
  z-index: -1;
  height: 280px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 18% 10%, rgba(0, 242, 255, 0.18), transparent 30%),
    radial-gradient(circle at 90% 0%, rgba(0, 118, 255, 0.16), transparent 28%),
    linear-gradient(180deg, rgba(4, 31, 60, 0.72), transparent);
  content: "";
  pointer-events: none;
}

.qr-print-hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  overflow: hidden;
  min-height: 156px;
  padding: 22px;
  border: 1px solid var(--qr-line);
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(7, 29, 51, 0.94), rgba(2, 12, 25, 0.96)),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.08) 0 1px, transparent 1px 44px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 22px 52px rgba(0, 18, 42, 0.22);
}

.qr-print-hero::after {
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.8), transparent);
  animation: qrScanline 4.8s linear infinite;
  content: "";
}

.qr-print-hero__copy span,
.qr-print-stat span,
.qr-print-group__head span {
  color: rgba(116, 245, 255, 0.78);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.qr-print-hero__copy h1 {
  margin: 8px 0 0;
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
  font-size: clamp(30px, 4vw, 48px);
  font-weight: 900;
  letter-spacing: -0.035em;
  text-shadow: 0 0 26px rgba(0, 242, 255, 0.18);
}

.qr-print-hero__actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.qr-print-hero__signal {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: var(--qr-accent);
  box-shadow: 0 0 0 6px rgba(0, 242, 255, 0.12), 0 0 22px rgba(0, 242, 255, 0.55);
  animation: qrPulse 1.8s ease-out infinite;
}

.qr-print-hero__button {
  min-height: 42px;
  border: 0;
  border-radius: 9px;
  background:
    linear-gradient(180deg, rgba(116, 245, 255, 1), rgba(0, 185, 214, 0.92)),
    var(--qr-accent);
  color: #00252b;
  font-weight: 900;
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.24);
}

.qr-print-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.qr-print-stat {
  position: relative;
  min-height: 104px;
  display: grid;
  align-content: space-between;
  overflow: hidden;
  padding: 16px;
  border: 1px solid var(--qr-line);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.84), rgba(3, 14, 27, 0.92)),
    radial-gradient(circle at 100% 0%, rgba(0, 242, 255, 0.12), transparent 34%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.qr-print-stat::after {
  position: absolute;
  inset: auto 14px 10px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.82), transparent);
  content: "";
}

.qr-print-stat strong {
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1;
}

.qr-print-stat.is-success::after {
  background: linear-gradient(90deg, rgba(78, 203, 138, 0.9), transparent);
}

.qr-print-stat.is-warning::after {
  background: linear-gradient(90deg, rgba(255, 171, 0, 0.9), transparent);
}

.qr-print-loading,
.qr-print-empty {
  min-height: 220px;
  display: grid;
  place-items: center;
  gap: 12px;
  border: 1px solid var(--qr-line);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(7, 29, 51, 0.82), rgba(2, 12, 25, 0.9));
  color: var(--qr-muted);
}

.qr-print-loading {
  grid-template-rows: auto auto;
}

.qr-print-loading span {
  width: 38px;
  height: 38px;
  border: 2px solid rgba(0, 242, 255, 0.18);
  border-top-color: var(--qr-accent);
  border-radius: 999px;
  animation: qrSpin 0.9s linear infinite;
}

.qr-print-groups {
  display: grid;
  gap: 18px;
}

.qr-print-group {
  position: relative;
  overflow: hidden;
  padding: 16px;
  border: 1px solid var(--qr-line);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(7, 29, 51, 0.86), rgba(2, 12, 25, 0.94)),
    var(--qr-panel);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 18px 44px rgba(0, 18, 42, 0.2);
  animation: qrCardEnter 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.qr-print-group__head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 2px 14px;
  border-bottom: 1px solid rgba(0, 242, 255, 0.12);
}

.qr-print-group h2 {
  margin: 0;
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
  font-size: 22px;
  letter-spacing: -0.02em;
}

.qr-print-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 14px;
  padding-top: 14px;
}

.qr-print-card {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 13px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.74), rgba(2, 12, 25, 0.9)),
    rgba(2, 12, 25, 0.82);
  text-align: center;
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.qr-print-card:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 242, 255, 0.34);
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.12);
}

.qr-print-card__qr {
  display: grid;
  place-items: center;
  width: 172px;
  height: 172px;
  margin: 0 auto;
  border-radius: 10px;
  background: #fff;
  box-shadow: inset 0 0 0 1px rgba(2, 12, 25, 0.08), 0 0 20px rgba(0, 242, 255, 0.14);
}

.qr-print-card__img {
  width: 160px;
  height: 160px;
}

.qr-print-card strong {
  overflow: hidden;
  color: rgba(225, 253, 255, 0.94);
  font-size: 16px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qr-print-card code {
  font-family: var(--xt-font-mono);
  font-size: 13px;
  color: #74f5ff;
}

.qr-print-card__url {
  color: var(--qr-muted);
  font-size: 12px;
  line-height: 1.45;
  word-break: break-all;
}

@keyframes qrScanline {
  0% { transform: translateX(-45%); opacity: 0.35; }
  50% { opacity: 1; }
  100% { transform: translateX(45%); opacity: 0.35; }
}

@keyframes qrPulse {
  0% { box-shadow: 0 0 0 0 rgba(0, 242, 255, 0.28), 0 0 22px rgba(0, 242, 255, 0.55); }
  100% { box-shadow: 0 0 0 14px rgba(0, 242, 255, 0), 0 0 22px rgba(0, 242, 255, 0.55); }
}

@keyframes qrSpin {
  to { transform: rotate(360deg); }
}

@keyframes qrCardEnter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 980px) {
  .qr-print-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .qr-print-page {
    padding-inline: 0;
  }

  .qr-print-hero,
  .qr-print-group {
    border-radius: 14px;
  }

  .qr-print-hero {
    align-items: stretch;
    flex-direction: column;
    min-height: 0;
  }

  .qr-print-hero__actions {
    justify-content: space-between;
  }

  .qr-print-stats {
    grid-template-columns: 1fr;
  }

  .qr-print-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .qr-print-hero::after,
  .qr-print-hero__signal,
  .qr-print-loading span,
  .qr-print-group {
    animation: none;
  }

  .qr-print-card {
    transition: none;
  }
}

@media print {
  .qr-print-page {
    display: block;
    max-width: none;
    padding: 0;
    color: #000;
    background: #fff;
  }

  .qr-print-page::before,
  .qr-print-hero__actions,
  .qr-print-stats,
  .qr-print-empty,
  .qr-print-loading {
    display: none;
  }

  .qr-print-hero,
  .qr-print-group {
    border: 0;
    border-radius: 0;
    padding: 0;
    background: #fff;
    box-shadow: none;
  }

  .qr-print-hero::after {
    display: none;
  }

  .qr-print-hero__copy span {
    color: #000;
  }

  .qr-print-hero__copy h1,
  .qr-print-group h2,
  .qr-print-card strong,
  .qr-print-card code,
  .qr-print-card__url {
    color: #000;
    text-shadow: none;
  }

  .qr-print-groups {
    gap: 12px;
  }

  .qr-print-group {
    margin-top: 12px;
    break-inside: avoid;
  }

  .qr-print-group__head {
    border-bottom: 1px solid #000;
    padding-bottom: 6px;
  }

  .qr-print-group__head span {
    color: #000;
  }

  .qr-print-grid {
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 10px;
    padding-top: 10px;
  }

  .qr-print-card {
    break-inside: avoid;
    border: 1px solid #000;
    border-radius: 0;
    padding: 10px;
    background: #fff;
    box-shadow: none;
  }

  .qr-print-card__qr {
    width: 150px;
    height: 150px;
    box-shadow: none;
  }

  .qr-print-card__img {
    width: 140px;
    height: 140px;
  }
}
</style>
