<template>
  <div class="mobile-shell ocr-vision" data-testid="mobile-ocr-capture">
    <div class="ocr-vision__hero mobile-top">
      <div class="ocr-vision__hero-copy">
        <span class="ocr-vision__eyebrow">OCR VISION</span>
        <h1>拍照识别</h1>
      </div>
      <div class="ocr-vision__hero-status">
        <span class="ocr-vision__led" :class="statusToneClass" aria-hidden="true"></span>
        <strong>{{ statusLabel }}</strong>
      </div>
    </div>

    <section class="ocr-vision__panel panel mobile-card">
      <header class="ocr-vision__panel-head">
        <div>
          <span class="ocr-vision__eyebrow">SHIFT SIGNAL</span>
          <strong>当前班次</strong>
        </div>
        <span class="ocr-vision__chip">{{ currentShift.shift_name || currentShift.shift_code || '待载入' }}</span>
      </header>
      <div v-if="loading" class="ocr-vision__state mobile-placeholder">
        <span class="ocr-vision__orbit" aria-hidden="true"></span>
        <strong>正在加载车间模板...</strong>
      </div>
      <div v-else-if="!currentShift.workshop_type" class="ocr-vision__state mobile-placeholder">
        <span class="ocr-vision__orbit is-muted" aria-hidden="true"></span>
        <strong>当前班次未识别到车间模板。</strong>
      </div>
      <div v-else-if="!template?.supports_ocr" class="ocr-vision__state mobile-placeholder">
        <span class="ocr-vision__orbit is-warning" aria-hidden="true"></span>
        <strong>当前车间模板未开启拍照识别。</strong>
      </div>
      <div v-else class="ocr-vision__readouts mobile-overview-grid">
        <div
          v-for="item in shiftReadouts"
          :key="item.label"
          class="ocr-vision__readout mobile-overview-item"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <section class="ocr-vision__panel ocr-vision__capture panel mobile-card">
      <header class="ocr-vision__panel-head">
        <div>
          <span class="ocr-vision__eyebrow">SCAN BAY</span>
          <strong>纸单拍照</strong>
        </div>
        <span class="ocr-vision__chip">{{ previewUrl ? '已取景' : '等待取景' }}</span>
      </header>
      <input
        ref="fileInput"
        class="mobile-ocr-input"
        type="file"
        accept="image/*"
        capture="environment"
        @change="handleFileChange"
      >
      <div class="ocr-vision__scanner mobile-ocr-capture">
        <div class="ocr-vision__viewfinder" :class="{ 'has-preview': previewUrl }">
          <span class="ocr-vision__corner is-top-left" aria-hidden="true"></span>
          <span class="ocr-vision__corner is-top-right" aria-hidden="true"></span>
          <span class="ocr-vision__corner is-bottom-left" aria-hidden="true"></span>
          <span class="ocr-vision__corner is-bottom-right" aria-hidden="true"></span>
          <span class="ocr-vision__scanline" aria-hidden="true"></span>
          <div v-if="!previewUrl" class="ocr-vision__lens">
            <span class="ocr-vision__lens-core" aria-hidden="true"></span>
            <strong>对准纸单</strong>
          </div>
        </div>
        <div v-if="previewUrl" class="ocr-vision__preview mobile-ocr-preview">
          <img :src="previewUrl" alt="识别预览图片">
        </div>
        <div class="ocr-vision__actions mobile-ocr-actions">
          <el-button
            type="primary"
            size="large"
            class="ocr-vision__primary-action"
            :loading="extracting"
            :disabled="loading || !template?.supports_ocr || submitCooldownActive"
            @click="triggerCapture"
          >
            拍照识别
          </el-button>
          <el-button
            v-if="previewUrl"
            plain
            class="ocr-vision__ghost-action"
            :disabled="extracting || submitCooldownActive"
            @click="triggerCapture"
          >
            重新拍照
          </el-button>
        </div>
      </div>
    </section>

    <section v-if="extractResult" class="ocr-vision__panel ocr-vision__result panel mobile-card">
      <header class="ocr-vision__panel-head">
        <div>
          <span class="ocr-vision__eyebrow">RESULT MATRIX</span>
          <strong>识别结果预览</strong>
        </div>
        <span class="ocr-vision__chip">{{ extractedFieldItems.length }} 项</span>
      </header>
      <div class="ocr-vision__confidence">
        <span class="is-good">{{ confidenceStats.good }}</span>
        <span class="is-warn">{{ confidenceStats.warn }}</span>
        <span class="is-danger">{{ confidenceStats.danger }}</span>
      </div>
      <div class="ocr-vision__result-grid mobile-ocr-grid">
        <div
          v-for="(item, index) in extractedFieldItems"
          :key="item.name"
          class="ocr-vision__field mobile-ocr-field"
          :class="`is-${confidenceTone(item.confidence)}`"
          :style="{ '--ocr-index': index }"
        >
          <div class="ocr-vision__field-top mobile-ocr-field__top">
            <strong>{{ item.label }}</strong>
            <span :class="['ocr-vision__badge', 'mobile-ocr-badge', `is-${confidenceTone(item.confidence)}`]">
              {{ confidenceLabel(item.confidence) }}
            </span>
          </div>
          <div class="ocr-vision__field-value mobile-ocr-field__value">{{ displayFieldValue(item.value) }}</div>
        </div>
      </div>

      <div v-if="extractResult.raw_text" class="ocr-vision__raw mobile-ocr-raw">
        <div class="ocr-vision__raw-title mobile-section-title">原始识别文本</div>
        <pre>{{ extractResult.raw_text }}</pre>
      </div>

    </section>

    <Teleport to="body">
      <div v-if="extractResult" class="ocr-vision__dock mobile-actions">
        <el-button type="primary" size="large" class="ocr-vision__primary-action" @click="goToDynamicForm">带入表单修正</el-button>
        <el-button plain size="large" class="ocr-vision__ghost-action" @click="goManualForm">改为手动填写</el-button>
      </div>
    </Teleport>

  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { isRetryableNetworkError, useRetryQueue } from '../../composables/useRetryQueue'
import { extractOcrFields, fetchCurrentShift, fetchWorkshopTemplate } from '../../api/mobile'
import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown } from '../../utils/submitGuard'

const STORAGE_PREFIX = 'aluminum-ocr-submission:'

const route = useRoute()
const router = useRouter()
const { enqueuePendingRequest } = useRetryQueue()
const fileInput = ref(null)
const loading = ref(true)
const extracting = ref(false)
const lastSubmitTime = ref(0)
const submitCooldownActive = ref(false)
const previewUrl = ref('')
const template = ref(null)
const extractResult = ref(null)
const currentShift = ref({})
let submitCooldownTimer = null

const extractedFieldItems = computed(() => {
  if (!template.value || !extractResult.value?.fields) return []
  const fieldMap = extractResult.value.fields || {}
  return [...(template.value.entry_fields || []), ...(template.value.extra_fields || [])]
    .map((field) => ({
      name: field.name,
      label: field.label,
      value: fieldMap[field.name]?.value ?? '',
      confidence: fieldMap[field.name]?.confidence ?? null
    }))
    .filter((item) => hasDisplayValue(item.value) || item.confidence !== null)
})
const shiftReadouts = computed(() => [
  { label: '业务日期', value: currentShift.value.business_date || '-' },
  { label: '班次', value: currentShift.value.shift_name || currentShift.value.shift_code || '-' },
  { label: '车间', value: template.value?.display_name || currentShift.value.workshop_name || '-' },
  { label: '节奏', value: template.value?.tempo === 'slow' ? '慢工序' : '快工序' }
])
const statusLabel = computed(() => {
  if (loading.value) return '载入中'
  if (!currentShift.value.workshop_type) return '待配置'
  if (!template.value?.supports_ocr) return '未开启'
  if (extracting.value) return '识别中'
  if (extractResult.value) return '已识别'
  return '就绪'
})
const statusToneClass = computed(() => {
  if (loading.value || extracting.value) return 'is-warn'
  if (!currentShift.value.workshop_type || !template.value?.supports_ocr) return 'is-danger'
  return 'is-good'
})
const confidenceStats = computed(() => {
  return extractedFieldItems.value.reduce((stats, item) => {
    const tone = confidenceTone(item.confidence)
    stats[tone] += 1
    return stats
  }, { good: 0, warn: 0, danger: 0 })
})

function requestErrorMessage(error, fallback = '识别失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

function storageKey(submissionId) {
  return `${STORAGE_PREFIX}${submissionId}`
}

function confidenceTone(confidence) {
  if (confidence === null || confidence === undefined) return 'warn'
  if (confidence >= 0.85) return 'good'
  if (confidence >= 0.6) return 'warn'
  return 'danger'
}

function confidenceLabel(confidence) {
  if (confidence === null || confidence === undefined) return '待核对'
  return `${Math.round(confidence * 100)}%`
}

function hasDisplayValue(value) {
  return value !== null && value !== undefined && value !== ''
}

function displayFieldValue(value) {
  return hasDisplayValue(value) ? value : '未识别'
}

function clearSubmitCooldownTimer() {
  if (submitCooldownTimer) {
    clearTimeout(submitCooldownTimer)
    submitCooldownTimer = null
  }
}

function startSubmitCooldown() {
  lastSubmitTime.value = Date.now()
  submitCooldownActive.value = true
  clearSubmitCooldownTimer()
  submitCooldownTimer = setTimeout(() => {
    submitCooldownActive.value = false
    submitCooldownTimer = null
  }, SUBMIT_COOLDOWN_MS)
}

function triggerCapture() {
  if (extracting.value) return
  if (isWithinSubmitCooldown(lastSubmitTime.value)) return
  fileInput.value?.click()
}

function rememberExtractedResult(payload) {
  sessionStorage.setItem(
    storageKey(payload.ocr_submission_id),
    JSON.stringify({
      ...payload,
      business_date: currentShift.value.business_date,
      shift_id: currentShift.value.shift_id
    })
  )
}

async function handleFileChange(event) {
  if (extracting.value) return
  if (isWithinSubmitCooldown(lastSubmitTime.value)) {
    event.target.value = ''
    return
  }
  const [file] = event.target.files || []
  if (!file) return

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = URL.createObjectURL(file)
  extracting.value = true
  try {
    const payload = await extractOcrFields(
      {
        workshopType: currentShift.value.workshop_code || currentShift.value.workshop_type,
        file
      },
      { skipErrorToast: true }
    )
    extractResult.value = payload
    rememberExtractedResult(payload)
    startSubmitCooldown()
    ElMessage.success('识别完成，请带入表单继续核对。')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      await enqueuePendingRequest({
        type: 'http',
        kind: 'form-data',
        method: 'post',
        url: '/ocr/extract',
        dedupeKey: `ocr-extract:${currentShift.value.workshop_code || currentShift.value.workshop_type || ''}:${currentShift.value.business_date || ''}:${file.name}:${file.size}`,
        formDataEntries: [
          { key: 'workshop_type', kind: 'text', value: currentShift.value.workshop_code || currentShift.value.workshop_type || '' },
          { key: 'file', kind: 'blob', value: file, filename: file.name || 'ocr-capture.jpg' }
        ]
      })
      startSubmitCooldown()
      ElMessage.success('已加入待同步队列，联网后请重新进入拍照识别查看结果')
      return
    }
    ElMessage.error(requestErrorMessage(error, '拍照识别失败'))
  } finally {
    extracting.value = false
    event.target.value = ''
  }
}

async function load() {
  loading.value = true
  try {
    const shiftPayload = await fetchCurrentShift()
    currentShift.value = shiftPayload
    const templateKey = shiftPayload?.workshop_code || shiftPayload?.workshop_type
    if (!templateKey) {
      template.value = null
      return
    }
    template.value = await fetchWorkshopTemplate(templateKey)
  } finally {
    loading.value = false
  }
}

function goToDynamicForm() {
  if (!extractResult.value?.ocr_submission_id) return
  rememberExtractedResult(extractResult.value)
  router.push({
    name: 'mobile-report-form',
    params: {
      businessDate: route.params.businessDate || currentShift.value.business_date,
      shiftId: route.params.shiftId || currentShift.value.shift_id
    },
    query: {
      ocr_submission_id: extractResult.value.ocr_submission_id
    }
  })
}

function goManualForm() {
  router.push({
    name: 'mobile-report-form',
    params: {
      businessDate: route.params.businessDate || currentShift.value.business_date,
      shiftId: route.params.shiftId || currentShift.value.shift_id
    }
  })
}

onMounted(load)

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
})
</script>

<style scoped>
.ocr-vision {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100vh;
  min-height: 100dvh;
  padding-bottom: calc(var(--xt-tabbar-height) + 116px + env(safe-area-inset-bottom, 0px));
}

.ocr-vision::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    radial-gradient(circle at 18% 0%, rgba(0, 242, 255, 0.16), transparent 34%),
    linear-gradient(120deg, transparent 0 44%, rgba(0, 242, 255, 0.08) 48%, transparent 54% 100%),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.034) 0 1px, transparent 1px 28px),
    repeating-linear-gradient(0deg, transparent 0 18px, rgba(0, 242, 255, 0.034) 19px 20px);
  opacity: 0.76;
  transform: translateX(-50%);
}

.ocr-vision > * {
  position: relative;
  z-index: 1;
}

.ocr-vision__hero,
.ocr-vision__panel,
.ocr-vision__field,
.ocr-vision__viewfinder,
.ocr-vision__dock {
  position: relative;
  overflow: hidden;
}

.ocr-vision__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: stretch;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
}

.ocr-vision__hero::after,
.ocr-vision__panel::after,
.ocr-vision__dock::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 0 40%, rgba(0, 242, 255, 0.12) 50%, transparent 60% 100%);
  opacity: 0;
  transform: translateX(-76%);
}

.ocr-vision__hero::after {
  animation: ocrVisionSweep 6.4s ease-in-out infinite;
}

.ocr-vision__hero-copy h1 {
  margin: 0;
  color: #e8fdff;
  font-family: var(--xt-font-display);
  font-size: 30px;
  font-weight: 950;
  letter-spacing: -0.04em;
  line-height: 1.05;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.18);
}

.ocr-vision__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: rgba(0, 242, 255, 0.86);
  font-size: 10px;
  font-weight: 950;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.ocr-vision__eyebrow::before,
.ocr-vision__led {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.72);
}

.ocr-vision__hero-status {
  display: grid;
  align-content: center;
  justify-items: end;
  gap: 8px;
  min-width: 84px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent),
    rgba(2, 10, 22, 0.44);
}

.ocr-vision__hero-status strong {
  color: #e8fdff;
  font-size: 13px;
  font-weight: 950;
  letter-spacing: 0.08em;
}

.ocr-vision__led {
  display: inline-block;
  animation: ocrVisionLed 1.8s ease-in-out infinite;
}

.ocr-vision__led.is-warn {
  background: #ffab00;
  box-shadow: 0 0 16px rgba(255, 171, 0, 0.64);
}

.ocr-vision__led.is-danger {
  background: #ff3d00;
  box-shadow: 0 0 16px rgba(255, 61, 0, 0.64);
}

.ocr-vision__panel {
  padding: 14px;
  border-radius: 18px;
}

.ocr-vision__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 2px 2px 14px;
}

.ocr-vision__panel-head strong {
  display: block;
  color: #e8fdff;
  font-size: 18px;
  font-weight: 950;
}

.ocr-vision__chip {
  padding: 4px 8px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: rgba(216, 249, 255, 0.86);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.ocr-vision__state {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 156px;
  text-align: center;
}

.ocr-vision__state strong {
  color: #e8fdff;
  font-size: 15px;
}

.ocr-vision__orbit,
.ocr-vision__lens-core {
  width: 66px;
  height: 66px;
  border-radius: 50%;
  border: 1px solid rgba(0, 242, 255, 0.34);
  background:
    radial-gradient(circle, rgba(0, 242, 255, 0.22) 0 18%, transparent 19%),
    conic-gradient(from 90deg, rgba(0, 242, 255, 0.82), transparent 38%, rgba(255, 171, 0, 0.36), transparent 76%, rgba(0, 242, 255, 0.82));
  box-shadow: 0 0 38px rgba(0, 242, 255, 0.13);
  animation: ocrVisionOrbit 5s linear infinite;
}

.ocr-vision__orbit.is-warning {
  border-color: rgba(255, 171, 0, 0.38);
}

.ocr-vision__orbit.is-muted {
  filter: grayscale(0.8);
  opacity: 0.66;
}

.ocr-vision__readouts {
  gap: 10px;
}

.ocr-vision__readout {
  min-height: 72px;
}

.ocr-vision__capture {
  border-color: rgba(0, 242, 255, 0.26);
}

.ocr-vision__result {
  overflow: visible;
}

.mobile-ocr-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.ocr-vision__scanner {
  display: grid;
  gap: 14px;
}

.ocr-vision__viewfinder {
  min-height: 220px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(0, 242, 255, 0.24);
  border-radius: 18px;
  background:
    radial-gradient(circle at 50% 38%, rgba(0, 242, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(0, 242, 255, 0.06), rgba(3, 12, 24, 0.7)),
    repeating-linear-gradient(0deg, transparent 0 14px, rgba(0, 242, 255, 0.04) 15px 16px);
  box-shadow: inset 0 0 42px rgba(0, 242, 255, 0.08), 0 16px 36px rgba(0, 0, 0, 0.2);
}

.ocr-vision__viewfinder.has-preview {
  min-height: 112px;
}

.ocr-vision__corner {
  position: absolute;
  width: 32px;
  height: 32px;
  border-color: rgba(0, 242, 255, 0.72);
  filter: drop-shadow(0 0 8px rgba(0, 242, 255, 0.4));
}

.ocr-vision__corner.is-top-left {
  top: 14px;
  left: 14px;
  border-top: 2px solid;
  border-left: 2px solid;
}

.ocr-vision__corner.is-top-right {
  top: 14px;
  right: 14px;
  border-top: 2px solid;
  border-right: 2px solid;
}

.ocr-vision__corner.is-bottom-left {
  bottom: 14px;
  left: 14px;
  border-bottom: 2px solid;
  border-left: 2px solid;
}

.ocr-vision__corner.is-bottom-right {
  right: 14px;
  bottom: 14px;
  border-right: 2px solid;
  border-bottom: 2px solid;
}

.ocr-vision__scanline {
  position: absolute;
  left: 18px;
  right: 18px;
  top: 22%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #00f2ff, transparent);
  box-shadow: 0 0 18px rgba(0, 242, 255, 0.76);
  animation: ocrVisionScanline 3.2s ease-in-out infinite;
}

.ocr-vision__lens {
  display: grid;
  justify-items: center;
  gap: 10px;
  color: var(--xt-text-secondary);
  font-weight: 900;
  letter-spacing: 0.08em;
}

.ocr-vision__preview {
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 16px;
  background: rgba(3, 12, 24, 0.7);
  overflow: hidden;
}

.ocr-vision__preview img {
  display: block;
  width: 100%;
  max-height: 240px;
  object-fit: contain;
}

.ocr-vision__actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
}

.ocr-vision__primary-action,
.ocr-vision__ghost-action {
  min-height: 44px;
}

.ocr-vision__primary-action {
  position: relative;
  overflow: hidden;
  font-weight: 950;
  letter-spacing: 0.04em;
}

.ocr-vision__primary-action::after {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.32), transparent);
  opacity: 0;
  transform: translateX(-110%);
}

.ocr-vision__confidence {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.ocr-vision__confidence span {
  min-height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 12px;
  background: rgba(2, 10, 22, 0.5);
  color: #e8fdff;
  font-family: var(--xt-font-number);
  font-weight: 950;
  font-variant-numeric: tabular-nums;
}

.ocr-vision__confidence span::before {
  margin-right: 4px;
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-body);
  font-size: 10px;
  letter-spacing: 0.08em;
}

.ocr-vision__confidence .is-good::before { content: 'GOOD'; }
.ocr-vision__confidence .is-warn::before { content: 'WARN'; }
.ocr-vision__confidence .is-danger::before { content: 'LOW'; }

.ocr-vision__result-grid {
  display: grid;
  gap: 10px;
}

.ocr-vision__field {
  padding: 13px;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent),
    rgba(2, 10, 22, 0.44);
  animation: ocrVisionCardIn 420ms ease both;
  animation-delay: calc(var(--ocr-index) * 60ms);
}

.ocr-vision__field.is-warn {
  border-color: rgba(255, 171, 0, 0.28);
}

.ocr-vision__field.is-danger {
  border-color: rgba(255, 61, 0, 0.32);
}

.ocr-vision__field-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ocr-vision__field-top strong {
  color: #e8fdff;
  font-size: 15px;
}

.ocr-vision__badge {
  min-width: 58px;
  padding: 4px 8px;
  border-radius: 999px;
  color: #06101f;
  font-size: 11px;
  font-weight: 950;
  text-align: center;
}

.ocr-vision__badge.is-good {
  background: #00f2ff;
}

.ocr-vision__badge.is-warn {
  background: #ffab00;
}

.ocr-vision__badge.is-danger {
  background: #ff3d00;
  color: #fff4ef;
}

.ocr-vision__field-value {
  margin-top: 8px;
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 850;
}

.ocr-vision__raw {
  margin-top: 14px;
}

.ocr-vision__raw-title {
  color: rgba(0, 242, 255, 0.84);
  font-size: 11px;
  font-weight: 950;
  letter-spacing: 0.12em;
}

.ocr-vision__raw pre {
  max-height: 160px;
  margin: 8px 0 0;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 14px;
  background: rgba(2, 10, 22, 0.62);
  color: rgba(216, 249, 255, 0.86);
  font-size: 12px;
  white-space: pre-wrap;
  overflow: auto;
}

.ocr-vision__dock {
  position: fixed;
  right: max(14px, calc((100vw - 600px) / 2 + 14px));
  bottom: calc(var(--xt-tabbar-height) + 14px + env(safe-area-inset-bottom, 0px));
  left: max(14px, calc((100vw - 600px) / 2 + 14px));
  z-index: 120;
  pointer-events: auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.08), rgba(3, 12, 24, 0.94)),
    rgba(3, 12, 24, 0.88);
  box-shadow: 0 -20px 50px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(16px);
}

@media (hover: hover) {
  .ocr-vision__primary-action:hover::after {
    animation: ocrVisionButtonSweep 620ms ease;
  }

  .ocr-vision__field:hover,
  .ocr-vision__viewfinder:hover {
    border-color: rgba(0, 242, 255, 0.34);
  }
}

.ocr-vision__primary-action:active,
.ocr-vision__ghost-action:active {
  transform: scale(0.97);
}

@keyframes ocrVisionSweep {
  0%, 62% {
    opacity: 0;
    transform: translateX(-76%);
  }
  76% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateX(76%);
  }
}

@keyframes ocrVisionScanline {
  0%, 100% {
    transform: translateY(-64px);
    opacity: 0.22;
  }
  48% {
    opacity: 1;
  }
  50% {
    transform: translateY(78px);
  }
}

@keyframes ocrVisionLed {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes ocrVisionOrbit {
  to {
    transform: rotate(360deg);
  }
}

@keyframes ocrVisionCardIn {
  from {
    opacity: 0;
    transform: translate3d(0, 12px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes ocrVisionButtonSweep {
  0% {
    opacity: 0;
    transform: translateX(-110%);
  }
  45% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateX(110%);
  }
}

@media (max-width: 420px) {
  .ocr-vision__hero {
    grid-template-columns: minmax(0, 1fr);
  }

  .ocr-vision__hero-status {
    justify-items: start;
  }

  .ocr-vision__viewfinder {
    min-height: 190px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ocr-vision__hero::after,
  .ocr-vision__scanline,
  .ocr-vision__led,
  .ocr-vision__orbit,
  .ocr-vision__lens-core,
  .ocr-vision__field {
    animation: none;
  }
}
</style>
