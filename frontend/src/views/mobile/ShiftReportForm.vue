<template>
  <div class="mobile-shell">
    <div class="mobile-top">
      <div>
        <div class="mobile-kicker">班长手机填报</div>
        <h1>班次填报</h1>
        <p>当前阶段先由主操手工录入原始值，系统自动校验、汇总和催报。</p>
      </div>
      <el-button plain @click="goEntry">返回入口</el-button>
    </div>

    <el-alert
      v-if="report.returned_reason"
      :title="`退回原因：${report.returned_reason}`"
      type="error"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-alert
      v-if="!canEdit"
      title="当前记录已提交或已进入系统确认状态，暂不允许继续修改。若需重填，请等待系统退回。"
      type="info"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-alert
      v-if="autoSavedLabel"
      :title="autoSavedLabel"
      type="info"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-card class="panel mobile-card">
      <template #header>班次基础信息</template>
      <div class="mobile-overview-grid">
        <div class="mobile-overview-item"><span>业务日期</span><strong>{{ report.business_date || '-' }}</strong></div>
        <div class="mobile-overview-item"><span>班次</span><strong>{{ report.shift_name || '-' }}</strong></div>
        <div class="mobile-overview-item"><span>车间</span><strong>{{ report.workshop_name || '-' }}</strong></div>
        <div class="mobile-overview-item"><span>班组</span><strong>{{ report.team_name || '-' }}</strong></div>
        <div class="mobile-overview-item"><span>班长</span><strong>{{ report.leader_name || auth.displayName }}</strong></div>
        <div class="mobile-overview-item">
          <span>状态</span>
          <el-tag :type="statusTagType(report.report_status)" effect="light">
            {{ formatStatusLabel(report.report_status) }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>当前提醒</template>
      <ReminderList :items="report.active_reminders || []" empty-text="当前没有催报记录。" />
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>生产填报区</template>
      <div class="mobile-form-grid">
        <div class="mobile-field">
          <label>出勤人数</label>
          <el-input v-model.number="form.attendance_count" :disabled="!canEdit" inputmode="numeric" placeholder="请输入人数" />
        </div>
        <div class="mobile-field">
          <label>投入量</label>
          <el-input v-model.number="form.input_weight" :disabled="!canEdit" inputmode="decimal" placeholder="请输入投入量" />
        </div>
        <div class="mobile-field">
          <label>产出量</label>
          <el-input v-model.number="form.output_weight" :disabled="!canEdit" inputmode="decimal" placeholder="请输入产出量" />
        </div>
        <div class="mobile-field">
          <label>废料量</label>
          <el-input v-model.number="form.scrap_weight" :disabled="!canEdit" inputmode="decimal" placeholder="请输入废料量" />
        </div>
        <div class="mobile-field">
          <label>备料量</label>
          <el-input v-model.number="form.storage_prepared" :disabled="!canEdit" inputmode="decimal" placeholder="请输入备料量" />
        </div>
        <div class="mobile-field">
          <label>成品入库</label>
          <el-input v-model.number="form.storage_finished" :disabled="!canEdit" inputmode="decimal" placeholder="请输入成品入库量" />
        </div>
        <div class="mobile-field">
          <label>发货量</label>
          <el-input v-model.number="form.shipment_weight" :disabled="!canEdit" inputmode="decimal" placeholder="请输入发货量" />
        </div>
        <div class="mobile-field">
          <label>合同承接量</label>
          <el-input v-model.number="form.contract_received" :disabled="!canEdit" inputmode="decimal" placeholder="请输入合同承接量" />
        </div>
      </div>
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>能耗填报区</template>
      <div class="mobile-form-grid">
        <div class="mobile-field">
          <label>日电耗</label>
          <el-input v-model.number="form.electricity_daily" :disabled="!canEdit" inputmode="decimal" placeholder="请输入日电耗" />
        </div>
        <div class="mobile-field">
          <label>日气耗</label>
          <el-input v-model.number="form.gas_daily" :disabled="!canEdit" inputmode="decimal" placeholder="请输入日气耗" />
        </div>
      </div>
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>异常备注区</template>
      <div class="mobile-form-grid">
        <div class="mobile-field mobile-field-inline">
          <label>是否异常</label>
          <el-switch v-model="form.has_exception" :disabled="!canEdit" />
        </div>
        <div class="mobile-field">
          <label>异常类型</label>
          <el-input v-model="form.exception_type" :disabled="!canEdit" placeholder="如设备、质量、人员、物流" />
        </div>
        <div class="mobile-field mobile-field-wide">
          <label>备注</label>
          <el-input
            v-model="form.note"
            :disabled="!canEdit"
            type="textarea"
            :rows="4"
            placeholder="请输入异常说明、交接信息或需要后续关注的内容"
          />
        </div>
        <div class="mobile-field mobile-field-wide">
          <label>现场照片</label>
          <div class="mobile-upload-box">
            <input
              ref="fileInputRef"
              type="file"
              accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              :disabled="!canEdit || uploadingPhoto"
              @change="handlePhotoSelected"
            />
            <div class="mobile-upload-meta">
              <div>已上传文件：{{ report.photo_file_name || '未上传' }}</div>
              <div>上传时间：{{ report.photo_uploaded_at || '-' }}</div>
            </div>
            <el-link v-if="report.photo_file_url" :href="report.photo_file_url" target="_blank" type="primary">查看已上传图片</el-link>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="panel mobile-card">
      <template #header>系统自动计算</template>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">月累计产量</div>
          <div class="stat-value">{{ formatNumber(report.monthly_output) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">月累计电耗</div>
          <div class="stat-value">{{ formatNumber(report.monthly_electricity) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">月累计气耗</div>
          <div class="stat-value">{{ formatNumber(report.monthly_gas) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">成材率</div>
          <div class="stat-value">{{ formatNumber(report.monthly_yield_rate) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">参考目标</div>
          <div class="stat-value">{{ formatNumber(report.target_value) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">昨日对比</div>
          <div class="stat-value">{{ formatNumber(report.compare_value) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">单吨电耗</div>
          <div class="stat-value">{{ formatNumber(report.energy_per_ton) }}</div>
        </div>
      </div>
    </el-card>

    <div class="mobile-sticky-actions">
      <el-button size="large" :disabled="Boolean(loadError) || !canEdit" @click="saveDraft" :loading="saving">暂存</el-button>
      <el-button type="primary" size="large" :disabled="submitDisabled" @click="submitFinal" :loading="submitting">提交</el-button>
    </div>

    <el-dialog v-model="restoreDialogVisible" title="发现本机暂存草稿" width="92%">
      <p>检测到当前班次存在未提交的本机草稿{{ restoreDraftSavedAt ? `（${restoreDraftSavedAt}）` : '' }}。</p>
      <p>你可以恢复继续填写，也可以丢弃草稿重新开始。</p>
      <template #footer>
        <el-button @click="discardDraft">丢弃草稿</el-button>
        <el-button type="primary" @click="restoreDraft">恢复草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchMobileReport,
  saveMobileReport,
  submitMobileReport,
  uploadMobileReportPhoto
} from '../../api/mobile'
import { useLocalDraft } from '../../composables/useLocalDraft'
import { isRetryableNetworkError, useRetryQueue } from '../../composables/useRetryQueue'
import { useAuthStore } from '../../stores/auth'
import { formatNumber, formatStatusLabel } from '../../utils/display'
import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown } from '../../utils/submitGuard'
import ReminderList from './ReminderList.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { enqueuePendingRequest } = useRetryQueue()
const saving = ref(false)
const submitting = ref(false)
const uploadingPhoto = ref(false)
const loadError = ref('')
const fileInputRef = ref(null)
const lastSubmitTime = ref(0)
const submitCooldownActive = ref(false)
const report = reactive({})
const form = reactive({
  business_date: '',
  shift_id: null,
  attendance_count: null,
  input_weight: null,
  output_weight: null,
  scrap_weight: null,
  storage_prepared: null,
  storage_finished: null,
  shipment_weight: null,
  contract_received: null,
  electricity_daily: null,
  gas_daily: null,
  has_exception: false,
  exception_type: '',
  note: '',
  optional_photo_url: ''
})
let submitCooldownTimer = null

const canEdit = computed(() => !['submitted', 'approved', 'auto_confirmed', 'locked'].includes(report.report_status))
const submitDisabled = computed(() => Boolean(loadError.value) || !canEdit.value || submitting.value || submitCooldownActive.value)

const localDraftScope = computed(() => ({
  workshopId: report.workshop_id || '',
  shiftId: form.shift_id || '',
  businessDate: form.business_date || '',
  machineId: '',
  trackingCardNo: ''
}))
const localDraftSnapshot = computed(() => ({
  form: {
    business_date: form.business_date,
    shift_id: form.shift_id,
    attendance_count: form.attendance_count,
    input_weight: form.input_weight,
    output_weight: form.output_weight,
    scrap_weight: form.scrap_weight,
    storage_prepared: form.storage_prepared,
    storage_finished: form.storage_finished,
    shipment_weight: form.shipment_weight,
    contract_received: form.contract_received,
    electricity_daily: form.electricity_daily,
    gas_daily: form.gas_daily,
    has_exception: form.has_exception,
    exception_type: form.exception_type,
    note: form.note,
    optional_photo_url: form.optional_photo_url
  }
}))

function statusTagType(status) {
  if (status === 'submitted' || status === 'approved' || status === 'auto_confirmed') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

function isMeaningfulLocalDraft(snapshot) {
  if (!snapshot?.form) return false
  return [
    'attendance_count',
    'input_weight',
    'output_weight',
    'scrap_weight',
    'storage_prepared',
    'storage_finished',
    'shipment_weight',
    'contract_received',
    'electricity_daily',
    'gas_daily',
    'exception_type',
    'note',
    'optional_photo_url'
  ].some((field) => {
    const value = snapshot.form[field]
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim() !== ''
    return true
  })
}

function applyLocalDraft(snapshot) {
  if (!snapshot?.form) return
  Object.assign(form, snapshot.form)
}

const {
  autoSavedLabel,
  checkForRestorableDraft,
  clearDraft,
  currentDraftKey,
  discardDraft,
  restoreDialogVisible,
  restoreDraft,
  restoreDraftSavedAt
} = useLocalDraft({
  scope: localDraftScope,
  snapshot: localDraftSnapshot,
  applyDraft: applyLocalDraft,
  enabled: computed(() => Boolean(form.business_date) && Boolean(form.shift_id)),
  isMeaningful: isMeaningfulLocalDraft
})

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

function assignForm(data) {
  Object.assign(report, data)
  form.business_date = data.business_date
  form.shift_id = Number(data.shift_id)
  form.attendance_count = data.attendance_count
  form.input_weight = data.input_weight
  form.output_weight = data.output_weight
  form.scrap_weight = data.scrap_weight
  form.storage_prepared = data.storage_prepared
  form.storage_finished = data.storage_finished
  form.shipment_weight = data.shipment_weight
  form.contract_received = data.contract_received
  form.electricity_daily = data.electricity_daily
  form.gas_daily = data.gas_daily
  form.has_exception = Boolean(data.has_exception)
  form.exception_type = data.exception_type || ''
  form.note = data.note || ''
  form.optional_photo_url = data.optional_photo_url || ''
}

async function load() {
  loadError.value = ''
  const data = await fetchMobileReport(route.params.businessDate, route.params.shiftId)
  assignForm(data)
}

function buildPayload() {
  return {
    business_date: form.business_date,
    shift_id: Number(form.shift_id),
    attendance_count: form.attendance_count,
    input_weight: form.input_weight,
    output_weight: form.output_weight,
    scrap_weight: form.scrap_weight,
    storage_prepared: form.storage_prepared,
    storage_finished: form.storage_finished,
    shipment_weight: form.shipment_weight,
    contract_received: form.contract_received,
    electricity_daily: form.electricity_daily,
    gas_daily: form.gas_daily,
    has_exception: form.has_exception,
    exception_type: form.exception_type || null,
    note: form.note || null,
    optional_photo_url: form.optional_photo_url || null
  }
}

function validateBeforeSubmit() {
  const requiredFields = [
    ['attendance_count', '出勤人数'],
    ['input_weight', '投入量'],
    ['output_weight', '产出量'],
    ['electricity_daily', '日电耗'],
    ['gas_daily', '日气耗']
  ]
  const missing = requiredFields.find(([field]) => form[field] === null || form[field] === '')
  if (missing) {
    ElMessage.warning(`请先填写：${missing[1]}`)
    return false
  }
  return true
}

async function queueMobileReport({ action, url, payload, clearDraftOnReplay = false }) {
  await enqueuePendingRequest({
    type: 'http-request',
    dedupeKey: `mobile-report:${action}:${payload.business_date}:${payload.shift_id}`,
    method: 'post',
    url,
    body: payload,
    clearDraftKey: clearDraftOnReplay ? currentDraftKey.value : undefined
  })
}

async function saveDraft() {
  saving.value = true
  try {
    const data = await saveMobileReport(buildPayload())
    assignForm(data)
    ElMessage.success('已暂存')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      await queueMobileReport({
        action: 'save',
        url: '/mobile/report/save',
        payload: buildPayload()
      })
      ElMessage.warning('网络不可用，已加入待同步队列并保留本机草稿')
      return
    }
    ElMessage.error(error?.response?.data?.detail || error?.message || '暂存失败')
  } finally {
    saving.value = false
  }
}

async function submitFinal() {
  if (isWithinSubmitCooldown(lastSubmitTime.value)) return
  if (!validateBeforeSubmit()) return
  submitting.value = true
  try {
    const data = await submitMobileReport(buildPayload())
    assignForm(data)
    clearDraft(currentDraftKey.value)
    startSubmitCooldown()
    ElMessage.success('提交成功，系统将自动校验并汇总')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      await queueMobileReport({
        action: 'submit',
        url: '/mobile/report/submit',
        payload: buildPayload(),
        clearDraftOnReplay: true
      })
      clearDraft(currentDraftKey.value)
      startSubmitCooldown()
      ElMessage.success('网络不可用，已加入待同步队列，联网后自动提交')
      return
    }
    ElMessage.error(error?.response?.data?.detail || error?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function handlePhotoSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploadingPhoto.value = true
  try {
    const payload = await uploadMobileReportPhoto({
      businessDate: form.business_date,
      shiftId: Number(form.shift_id),
      file
    })
    report.photo_file_name = payload.photo_file_name
    report.photo_file_path = payload.photo_file_path
    report.photo_file_url = payload.photo_file_url
    report.photo_uploaded_at = payload.uploaded_at
    form.optional_photo_url = payload.photo_file_url
    ElMessage.success('现场图片上传成功')
  } finally {
    uploadingPhoto.value = false
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
  }
}

function goEntry() {
  router.push({ name: 'mobile-entry' })
}

onMounted(async () => {
  try {
    await load()
    checkForRestorableDraft()
  } catch (error) {
    loadError.value = error?.response?.data?.detail || error?.message || '加载班次填报失败，请返回入口后重试。'
  }
})

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
})
</script>
