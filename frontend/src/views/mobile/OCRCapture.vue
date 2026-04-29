<template>
  <div class="mobile-shell" data-testid="mobile-ocr-capture">
    <div class="mobile-top">
      <div>
        <h1>拍照识别</h1>
        <p>纸单拍照后先识别，再带入同一套随行卡表单继续人工核对和提交。</p>
      </div>
    </div>

    <el-card class="panel mobile-card">
      <template #header>当前班次</template>
      <div v-if="loading" class="mobile-placeholder">正在加载车间模板...</div>
      <div v-else-if="!currentShift.workshop_type" class="mobile-placeholder">当前班次未识别到车间模板。</div>
      <div v-else-if="!template?.supports_ocr" class="mobile-placeholder">
        当前车间模板未开启拍照识别，请返回入口改用手动填写。
      </div>
      <div v-else class="mobile-overview-grid">
        <div class="mobile-overview-item">
          <span>业务日期</span>
          <strong>{{ currentShift.business_date || '-' }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>班次</span>
          <strong>{{ currentShift.shift_name || currentShift.shift_code || '-' }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>车间</span>
          <strong>{{ template.display_name || currentShift.workshop_name || '-' }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>节奏</span>
          <strong>{{ template.tempo === 'slow' ? '慢工序' : '快工序' }}</strong>
        </div>
      </div>
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>纸单拍照</template>
      <input
        ref="fileInput"
        class="mobile-ocr-input"
        type="file"
        accept="image/*"
        capture="environment"
        @change="handleFileChange"
      >
      <div class="mobile-ocr-capture">
        <div v-if="previewUrl" class="mobile-ocr-preview">
          <img :src="previewUrl" alt="识别预览图片">
        </div>
        <div class="mobile-ocr-actions">
          <el-button
            type="primary"
            size="large"
            :loading="extracting"
            :disabled="loading || !template?.supports_ocr || submitCooldownActive"
            @click="triggerCapture"
          >
            拍照识别
          </el-button>
          <el-button v-if="previewUrl" plain :disabled="extracting || submitCooldownActive" @click="triggerCapture">重新拍照</el-button>
          <div class="mobile-field-meta">
            建议完整拍到纸单边缘，数字字段识别后会按置信度标色，仍需人工复核。
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="extractResult" class="panel mobile-card">
      <template #header>识别结果预览</template>
      <div class="mobile-ocr-grid">
        <div
          v-for="item in extractedFieldItems"
          :key="item.name"
          class="mobile-ocr-field"
        >
          <div class="mobile-ocr-field__top">
            <strong>{{ item.label }}</strong>
            <span :class="['mobile-ocr-badge', `is-${confidenceTone(item.confidence)}`]">
              {{ confidenceLabel(item.confidence) }}
            </span>
          </div>
          <div class="mobile-ocr-field__value">{{ item.value || '未识别' }}</div>
        </div>
      </div>

      <div v-if="extractResult.raw_text" class="mobile-ocr-raw">
        <div class="mobile-section-title">原始识别文本</div>
        <pre>{{ extractResult.raw_text }}</pre>
      </div>

      <div class="mobile-actions">
        <el-button type="primary" size="large" @click="goToDynamicForm">带入表单修正</el-button>
        <el-button plain size="large" @click="goManualForm">改为手动填写</el-button>
      </div>
    </el-card>

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
    .filter((item) => item.value || item.confidence !== null)
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
