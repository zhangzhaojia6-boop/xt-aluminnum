<template>
  <div class="mobile-shell mobile-shell--flow">
    <div class="mobile-top">
      <div>
        <div v-if="false" class="mobile-kicker">04 填报流程页</div>
        <h1>本班填报</h1>
      </div>
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
      title="当前记录已提交，暂时不能继续修改。需要重填时，等系统退回。"
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
    <div v-if="loadError" class="mobile-recovery-actions">
      <el-button type="primary" :loading="loading" @click="load">重试加载</el-button>
      <el-button plain @click="goEntry">返回首页</el-button>
    </div>

    <div v-else-if="loading" class="mobile-inline-state panel">
      <p>正在加载班次填报内容…</p>
      <p>若持续无响应，请退出后重进或联系管理员。</p>
      <el-button type="primary" plain class="mobile-inline-action" @click="load">再次尝试</el-button>
    </div>

    <div v-if="!loadError && !loading" class="entry-flow-steps" aria-label="填报步骤">
      <span
        v-for="(step, index) in entryFlowSteps"
        :key="step"
        :class="{ 'is-active': index <= entryStepActiveIndex }"
      >
        <b>{{ index + 1 }}</b>{{ step }}
      </span>
    </div>

    <div v-if="!loadError && !loading" class="entry-flow-layout">
      <MobileSwipeWorkspace
        v-model:active-key="activePageKey"
        :pages="swipePages"
        data-testid="mobile-shift-report-workspace"
      >
        <template #overview>
          <el-card class="panel mobile-card">
            <template #header>当前任务</template>
          <div class="mobile-overview-grid">
            <div class="mobile-overview-item"><span>业务日期</span><strong>{{ report.business_date || '-' }}</strong></div>
            <div class="mobile-overview-item"><span>班次</span><strong>{{ report.shift_name || '-' }}</strong></div>
            <div class="mobile-overview-item"><span>车间</span><strong>{{ report.workshop_name || '-' }}</strong></div>
            <div class="mobile-overview-item"><span>班组</span><strong>{{ report.team_name || '-' }}</strong></div>
            <div class="mobile-overview-item"><span>负责人</span><strong>{{ report.leader_name || auth.displayName }}</strong></div>
            <div class="mobile-overview-item">
              <span>状态</span>
              <el-tag :type="statusTagType(report.report_status)" effect="light">
                {{ formatStatusLabel(report.report_status) }}
              </el-tag>
            </div>
          </div>
        </el-card>

        <el-card v-if="agentDecisionHint" class="panel mobile-card">
          <template #header>系统处理</template>
          <div class="mobile-overview-grid">
            <div class="mobile-overview-item">
              <span>结果</span>
              <el-tag :type="agentDecisionTagType" effect="light">{{ agentDecisionTitle }}</el-tag>
            </div>
            <div class="mobile-overview-item mobile-overview-item-wide">
              <span>说明</span>
              <strong>{{ agentDecisionHint }}</strong>
            </div>
          </div>
        </el-card>

        <el-card class="panel mobile-card">
          <template #header>提醒</template>
          <ReminderList :items="report.active_reminders || []" empty-text="当前没有提醒。" />
          </el-card>
        </template>

      <template #production>
        <el-card class="panel mobile-card">
          <template #header>本班关键数字</template>
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
              <label>
                废料量
                <span class="entry-calc-source">{{ scrapOverrideLabel }}</span>
              </label>
              <el-input v-model.number="form.scrap_weight" :disabled="!canEdit" inputmode="decimal" placeholder="请输入废料量" />
            </div>
          </div>

          <div class="entry-calc-strip">
            <div>
              <span>建议废料</span>
              <strong>{{ suggestedScrapDisplay }}</strong>
              <em>自动计算</em>
            </div>
            <div>
              <span>成品率</span>
              <strong>{{ yieldRateDisplay }}</strong>
              <em>{{ scrapOverrideLabel }}</em>
            </div>
          </div>

          <div class="mobile-actions">
            <el-button text type="primary" @click="showExtendedProduction = !showExtendedProduction">
              {{ showExtendedProduction ? '收起补录字段' : '展开补录字段' }}
            </el-button>
          </div>

          <el-collapse-transition>
            <div v-if="showExtendedProduction" class="mobile-form-grid">
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
          </el-collapse-transition>
          <div class="mobile-history-note">补录字段可留空，系统会结合专项岗位数据自动汇总。</div>
        </el-card>
      </template>

      <template #energy>
        <el-card class="panel mobile-card">
          <template #header>能耗原始值</template>
          <div class="mobile-form-grid">
            <div class="mobile-field">
              <label>日电耗</label>
              <el-input v-model.number="form.electricity_daily" :disabled="!canEdit" inputmode="decimal" placeholder="请输入日电耗（可选）" />
            </div>
            <div class="mobile-field">
              <label>日气耗</label>
              <el-input v-model.number="form.gas_daily" :disabled="!canEdit" inputmode="decimal" placeholder="请输入日气耗（可选）" />
            </div>
          </div>
        </el-card>
      </template>

      <template #exception>
        <el-card class="panel mobile-card">
          <template #header>异常与备注</template>
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
      </template>

      <template #submit>
        <el-card class="panel mobile-card">
          <template #header>提交确认</template>
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
              <div class="stat-label">昨日对比</div>
              <div class="stat-value">{{ formatNumber(report.compare_value) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">单吨电耗</div>
              <div class="stat-value">{{ formatNumber(report.energy_per_ton) }}</div>
            </div>
          </div>
        </el-card>
      </template>
      </MobileSwipeWorkspace>

    </div>

    <div v-if="!loadError && !loading" class="mobile-sticky-actions">
      <div class="note">{{ currentPage.title }} · {{ currentPageIndex + 1 }} / {{ swipePages.length }}</div>
      <div class="mobile-sticky-actions__buttons">
        <el-button
          v-if="!isFirstPage"
          size="large"
          :disabled="Boolean(loadError) || saving || submitting || loading"
          @click="goPrevPage"
        >
          上一步
        </el-button>
        <el-button
          size="large"
          :disabled="Boolean(loadError) || !canEdit || loading"
          @click="saveDraft"
          :loading="saving"
          class="mobile-inline-action"
        >
          保存草稿
        </el-button>
        <el-button
          v-if="!isLastPage"
          type="primary"
          size="large"
          :disabled="Boolean(loadError) || saving || submitting || loading"
          @click="goNextPage"
        >
          下一步
        </el-button>
        <el-button
          v-else
          type="primary"
          size="large"
          :disabled="submitDisabled || loading"
          @click="submitFinal"
          :loading="submitting"
          class="mobile-inline-action"
        >
          正式提交
        </el-button>
      </div>
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
import MobileSwipeWorkspace from '../../components/mobile/MobileSwipeWorkspace.vue'
import ReminderList from './ReminderList.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { enqueuePendingRequest } = useRetryQueue()
const saving = ref(false)
const submitting = ref(false)
const uploadingPhoto = ref(false)
const loadError = ref('')
const loading = ref(false)
const fileInputRef = ref(null)
const lastSubmitTime = ref(0)
const submitCooldownActive = ref(false)
const activePageKey = ref('overview')
const showExtendedProduction = ref(false)
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
const agentDecisionStatus = computed(() => report.agent_decision_status || '')
const agentDecisionTagType = computed(() => {
  if (agentDecisionStatus.value === 'auto_confirmed') return 'success'
  if (agentDecisionStatus.value === 'returned') return 'danger'
  if (agentDecisionStatus.value === 'submitted') return 'warning'
  return 'info'
})
const agentDecisionTitle = computed(() => {
  if (agentDecisionStatus.value === 'auto_confirmed') return '已自动确认'
  if (agentDecisionStatus.value === 'returned') return '已自动退回'
  if (agentDecisionStatus.value === 'submitted') return '系统处理中'
  return '待处理'
})
const agentDecisionHint = computed(() => {
  const reason = (report.agent_decision_reason || '').trim()
  if (reason) return reason
  if (report.returned_reason) return report.returned_reason
  if (agentDecisionStatus.value === 'auto_confirmed') return '数据已通过校验并进入自动汇总。'
  if (agentDecisionStatus.value === 'submitted') return '系统已接收提交，正在自动校验。'
  return ''
})
const swipePages = [
  { key: 'overview', title: '班次' },
  { key: 'production', title: '数字' },
  { key: 'energy', title: '能耗' },
  { key: 'exception', title: '异常' },
  { key: 'submit', title: '确认' }
]
const entryFlowSteps = ['班次信息', '产品录入', '配比/物耗', '异常补充', '图片/附件', '提交成功']
const stepTipMap = {
  overview: ['核对业务日期、班次和车间。', '确认当前状态可继续编辑。', '有退回原因时先按提示补齐。'],
  production: ['优先填写投入量、产出量和废料量。', '必填数字为空时无法正式提交。', '补录字段可留空，系统会自动汇总。'],
  energy: ['电耗、气耗为可选原始值。', '能耗异常请在异常步骤补充说明。'],
  exception: ['异常类型请写明设备、质量、人员或物流。', '图片/附件只作为现场凭证，不强制依赖 OCR。'],
  submit: ['提交前确认关键数字。', '提交后系统自动校验，结果以审阅端为准。']
}
const assistHintMap = {
  overview: '系统提示：当前班次信息来自已登录账号与排班数据。',
  production: '辅助提示：产出量与投入量偏差较大时，请补充异常说明。',
  energy: '辅助提示：能耗数据用于经营分析，不作为财务结算。',
  exception: '辅助提示：AI/OCR 不稳定时请以人工填写为准。',
  submit: '系统提示：保存草稿不会进入审阅队列，正式提交后才流转。'
}
const currentPageIndex = computed(() => swipePages.findIndex((page) => page.key === activePageKey.value))
const currentPage = computed(() => swipePages[Math.max(currentPageIndex.value, 0)] || swipePages[0])
const isFirstPage = computed(() => currentPageIndex.value <= 0)
const isLastPage = computed(() => currentPageIndex.value >= swipePages.length - 1)
const entryStepActiveIndex = computed(() => Math.min(currentPageIndex.value, entryFlowSteps.length - 1))
const currentStepTips = computed(() => stepTipMap[activePageKey.value] || stepTipMap.overview)
const currentAssistHint = computed(() => assistHintMap[activePageKey.value] || assistHintMap.overview)
const suggestedScrap = computed(() => {
  const input = Number(form.input_weight)
  const output = Number(form.output_weight)
  if (!Number.isFinite(input) || !Number.isFinite(output)) return null
  const value = input - output
  if (value < 0) return null
  return Number(value.toFixed(2))
})
const hasManualScrapOverride = computed(() => {
  if (suggestedScrap.value === null) return false
  const actual = Number(form.scrap_weight)
  if (!Number.isFinite(actual)) return false
  return Math.abs(actual - suggestedScrap.value) > 0.005
})
const suggestedScrapDisplay = computed(() => suggestedScrap.value === null ? '-' : formatNumber(suggestedScrap.value))
const scrapOverrideLabel = computed(() => hasManualScrapOverride.value ? '人工修正' : '系统建议')
const yieldRateDisplay = computed(() => {
  const input = Number(form.input_weight)
  const output = Number(form.output_weight)
  if (!Number.isFinite(input) || !Number.isFinite(output) || input <= 0) return '-'
  return `${((output / input) * 100).toFixed(2)}%`
})

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
  showExtendedProduction.value = [
    data.storage_prepared,
    data.storage_finished,
    data.shipment_weight,
    data.contract_received,
  ].some((value) => value !== null && value !== undefined && value !== '')
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await fetchMobileReport(route.params.businessDate, route.params.shiftId)
    assignForm(data)
  } catch (error) {
    loadError.value = requestErrorMessage(error, '加载班次填报失败，请返回入口后重试。')
    throw error
  } finally {
    loading.value = false
  }
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
    ['output_weight', '产出量']
  ]
  const missing = requiredFields.find(([field]) => form[field] === null || form[field] === '')
  if (missing) {
    ElMessage.warning(`请先填写：${missing[1]}`)
    return false
  }
  return true
}

function requestErrorMessage(error, fallback = '操作失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  return detail || error?.message || fallback
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
    ElMessage.error(requestErrorMessage(error, '暂存失败'))
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
    ElMessage.success('提交成功，系统会自动处理')
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
    ElMessage.error(requestErrorMessage(error, '提交失败'))
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
  } catch (error) {
    ElMessage.error(requestErrorMessage(error, '图片上传失败，请重试'))
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

function goPrevPage() {
  const prev = swipePages[currentPageIndex.value - 1]
  if (prev) activePageKey.value = prev.key
}

function goNextPage() {
  const next = swipePages[currentPageIndex.value + 1]
  if (next) activePageKey.value = next.key
}

onMounted(async () => {
  try {
    await load()
    checkForRestorableDraft()
  } catch (error) {
    loadError.value = requestErrorMessage(error, '加载班次填报失败，请返回入口后重试。')
  }
})

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
})
</script>

<style scoped>
.mobile-shell--flow {
  max-width: 1180px;
  margin: 0 auto;
  padding-bottom: 96px;
}

.entry-flow-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 12px;
  padding: 12px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card);
  background: #fff;
}

.entry-flow-steps span {
  display: grid;
  justify-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}

.entry-flow-steps b {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid #cbd7e7;
  border-radius: 999px;
  color: var(--text-secondary);
  background: #fff;
}

.entry-flow-steps .is-active {
  color: var(--primary);
}

.entry-flow-steps .is-active b {
  color: #fff;
  border-color: transparent;
  background: linear-gradient(135deg, #0071e3, #5856d6);
}

.entry-flow-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}

.entry-flow-hints {
  position: sticky;
  top: 12px;
  display: grid;
  gap: 12px;
}

.entry-flow-hint-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card);
  background: #fff;
  box-shadow: var(--shadow-card);
}

.entry-flow-hint-card strong {
  color: var(--primary);
  font-size: 16px;
  font-family: var(--font-display, 'SF Pro Display', system-ui);
}

.entry-flow-hint-card ol {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
}

.entry-flow-hint-card span {
  color: var(--text-secondary);
  line-height: 1.6;
}

.entry-calc-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.entry-calc-strip div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: #f8fbff;
}

.entry-calc-strip span,
.entry-calc-strip em,
.entry-calc-source {
  color: var(--text-muted);
  font-size: 12px;
  font-style: normal;
}

.entry-calc-strip strong {
  color: var(--primary);
  font-family: var(--font-number);
  font-size: 24px;
  line-height: 1;
}

.entry-calc-source {
  margin-left: 6px;
  font-weight: 800;
}

.mobile-shell--flow :deep(.mobile-field .el-input__wrapper),
.mobile-shell--flow :deep(.mobile-field .el-textarea__inner) {
  min-height: 44px;
  border-radius: var(--radius-control);
}

.mobile-shell--flow :deep(.mobile-sticky-actions) {
  position: sticky;
  bottom: 0;
  z-index: 12;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card) var(--radius-card) 0 0;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  box-shadow: 0 -8px 20px rgba(15, 45, 84, 0.08);
}

.mobile-shell--flow :deep(.mobile-sticky-actions .el-button--primary) {
  box-shadow: 0 4px 24px rgba(0, 113, 227, 0.3);
  transition: box-shadow 0.2s, transform 0.2s;
}

.mobile-shell--flow :deep(.mobile-sticky-actions .el-button--primary:hover) {
  box-shadow: 0 8px 40px rgba(0, 113, 227, 0.5);
  transform: translateY(-1px);
}

@media (max-width: 900px) {
  .entry-flow-layout {
    grid-template-columns: 1fr;
  }

  .entry-flow-hints {
    position: static;
    order: 2;
  }

  .entry-flow-steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 420px) {
  .mobile-shell--flow {
    padding-inline: 10px;
  }

  .entry-flow-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 10px;
  }

  .entry-flow-hint-card {
    padding: 12px;
  }

  .entry-calc-strip {
    grid-template-columns: 1fr;
  }
}
</style>
