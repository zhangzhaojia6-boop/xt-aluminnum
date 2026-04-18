<template>
  <div class="mobile-shell" data-testid="attendance-confirm">
    <div class="mobile-top">
      <div>
        <div class="mobile-kicker">班长二次确认</div>
        <h1>考勤确认</h1>
        <p>先看钉钉原始打卡，再由班长确认或纠偏，异常会自动进入人事复核。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="loadPage">刷新</el-button>
        <el-button plain @click="goEntry">返回入口</el-button>
      </div>
    </div>

    <el-card class="panel mobile-card">
      <template #header>当前班次</template>
      <div v-if="pageLoading" class="mobile-placeholder">正在加载当前班次与机台...</div>
      <div v-else-if="!currentShift.shift_id" class="mobile-placeholder">当前账号没有可确认的班次。</div>
      <div v-else class="mobile-overview-grid">
        <div class="mobile-overview-item">
          <span>业务日期</span>
          <strong>{{ currentShift.business_date }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>班次</span>
          <strong>{{ currentShift.shift_name || currentShift.shift_code || '-' }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>车间</span>
          <strong>{{ currentShift.workshop_name || '-' }}</strong>
        </div>
        <div class="mobile-overview-item">
          <span>当前状态</span>
          <strong>{{ attendanceStatusLabel }}</strong>
        </div>
      </div>
    </el-card>

    <el-card v-if="currentShift.shift_id" class="panel mobile-card">
      <template #header>确认范围</template>
      <div class="mobile-form-grid">
        <div class="mobile-field mobile-field-wide">
          <label>
            <span class="mobile-required">*</span>
            机台
          </label>
          <el-select
            v-model="machineId"
            placeholder="请选择机台"
            filterable
            :disabled="locked"
          >
            <el-option
              v-for="machine in equipmentOptions"
              :key="machine.id"
              :label="machine.name"
              :value="machine.id"
            />
          </el-select>
          <div class="mobile-field-meta">
            当前应到 {{ headcount }} 人
            <span v-if="draftPayload.status === 'confirmed' || draftPayload.status === 'hr_reviewed'">
              ，本机台已确认
            </span>
          </div>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="!pageLoading && currentShift.shift_id && currentShift.attendance_exception_count"
      class="panel"
      type="warning"
      :closable="false"
      show-icon
      :title="`本班已存在 ${currentShift.attendance_exception_count} 条考勤差异，提交后会进入人事复核。`"
    />

    <el-card v-if="currentShift.shift_id && machineId" class="panel mobile-card">
      <template #header>
        <div class="mobile-attendance-header">
          <div>
            <strong>{{ selectedMachineName || '机台' }}</strong>
            <span>{{ currentShift.shift_name || currentShift.shift_code || '-' }}</span>
            <span>{{ currentShift.business_date }}</span>
          </div>
          <el-tag :type="locked ? 'success' : 'warning'" effect="light">
            {{ locked ? '已确认' : '待确认' }}
          </el-tag>
        </div>
      </template>

      <div v-if="draftLoading" class="mobile-placeholder">正在加载钉钉打卡与班组名单...</div>
      <el-empty
        v-else-if="!rows.length"
        description="当前机台没有班组名单或打卡草稿，请先确认排班和钉钉同步。"
      />
      <div v-else class="mobile-attendance-list">
        <section
          v-for="row in rows"
          :key="row.employee_id"
          :class="['mobile-attendance-card', { 'is-anomaly': isAnomaly(row) }]"
        >
          <div class="mobile-attendance-card__top">
            <div>
              <div class="mobile-attendance-card__name">{{ row.employee_name || row.employee_no }}</div>
              <div class="mobile-attendance-card__clock">
                钉钉：{{ formatClock(row) }}
              </div>
            </div>
            <el-tag :type="isAnomaly(row) ? 'danger' : 'success'" effect="light">
              {{ isAnomaly(row) ? '异常' : '正常' }}
            </el-tag>
          </div>

          <div class="mobile-field">
            <label>确认状态</label>
            <el-select
              v-model="row.leader_status"
              placeholder="请选择状态"
              :disabled="locked"
              @change="handleStatusChange(row)"
            >
              <el-option
                v-for="option in statusOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>

          <div v-if="row.late_minutes || row.early_leave_minutes" class="mobile-attendance-card__metrics">
            <span v-if="row.late_minutes">迟到 {{ row.late_minutes }} 分</span>
            <span v-if="row.early_leave_minutes">早退 {{ row.early_leave_minutes }} 分</span>
          </div>

          <div class="mobile-field" v-if="overrideReasonRequired(row)">
            <label>
              <span class="mobile-required">*</span>
              差异原因
            </label>
            <el-input
              v-model="row.override_reason"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              :disabled="locked"
              placeholder="班长修改自动判定时必须说明原因"
            />
          </div>

          <div class="mobile-field">
            <label>备注</label>
            <el-input
              v-model="row.notes"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              :disabled="locked"
              placeholder="补充说明，如请假单号、外出地点等"
            />
          </div>
        </section>
      </div>
    </el-card>

    <div class="mobile-sticky-actions">
      <el-button size="large" @click="loadDraft" :disabled="!machineId" :loading="draftLoading">重新拉取</el-button>
      <el-button
        type="primary"
        size="large"
        :disabled="submitDisabled"
        :loading="submitting"
        @click="submit"
      >
        提交确认
      </el-button>
    </div>

    <MobileBottomNav />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { fetchAttendanceDraft, submitAttendanceConfirmation } from '../../api/attendance'
import { isRetryableNetworkError, useRetryQueue } from '../../composables/useRetryQueue'
import { fetchEquipment } from '../../api/master'
import { fetchCurrentShift } from '../../api/mobile'
import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown } from '../../utils/submitGuard'
import MobileBottomNav from './MobileBottomNav.vue'

const router = useRouter()
const { enqueuePendingRequest } = useRetryQueue()

const pageLoading = ref(true)
const draftLoading = ref(false)
const submitting = ref(false)
const lastSubmitTime = ref(0)
const submitCooldownActive = ref(false)
const currentShift = ref({})
const equipmentOptions = ref([])
const machineId = ref(null)
const draftPayload = ref({ status: 'draft', items: [] })
const rows = ref([])
let submitCooldownTimer = null

const statusOptions = [
  { value: 'present', label: '出勤' },
  { value: 'absent', label: '缺勤' },
  { value: 'late', label: '迟到' },
  { value: 'early_leave', label: '早退' },
  { value: 'on_leave', label: '请假' },
  { value: 'business_trip', label: '出差' }
]

const headcount = computed(() => Number(draftPayload.value?.headcount_expected || rows.value.length || 0))
const locked = computed(() => ['confirmed', 'hr_reviewed'].includes(draftPayload.value?.status))
const selectedMachineName = computed(() => {
  return equipmentOptions.value.find((item) => item.id === machineId.value)?.name || currentShift.value.attendance_machine_name || ''
})
const attendanceStatusLabel = computed(() => {
  if (locked.value) return '已确认'
  if (Number(currentShift.value?.attendance_exception_count || 0) > 0) return '存在异常'
  if (currentShift.value?.attendance_status === 'not_started') return '未确认'
  return '待确认'
})
const submitDisabled = computed(() => {
  if (!machineId.value || !rows.value.length || locked.value || submitCooldownActive.value) return true
  return rows.value.some((row) => {
    if (!row.leader_status) return true
    return overrideReasonRequired(row) && !String(row.override_reason || '').trim()
  })
})

function requestErrorMessage(error, fallback = '提交失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  return detail || error?.message || fallback
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

function formatClock(row) {
  if (!row.dingtalk_clock_in && !row.dingtalk_clock_out) return '无记录'
  return `${row.dingtalk_clock_in || '--'} → ${row.dingtalk_clock_out || '--'}`
}

function isAnomaly(row) {
  return String(row.leader_status || '') !== String(row.auto_status || '')
}

function overrideReasonRequired(row) {
  return isAnomaly(row)
}

function handleStatusChange(row) {
  if (!overrideReasonRequired(row)) {
    row.override_reason = ''
  }
}

function normalizeDraft(payload) {
  draftPayload.value = payload || { status: 'draft', items: [] }
  rows.value = (payload?.items || []).map((item) => ({
    ...item,
    leader_status: item.leader_status || item.auto_status || 'present',
    override_reason: item.override_reason || '',
    notes: item.notes || ''
  }))
}

async function loadDraft() {
  if (!currentShift.value?.shift_id || !machineId.value) {
    normalizeDraft({ status: 'draft', items: [] })
    return
  }

  draftLoading.value = true
  try {
    const payload = await fetchAttendanceDraft({
      machine_id: machineId.value,
      shift_id: currentShift.value.shift_id,
      business_date: currentShift.value.business_date
    })
    normalizeDraft(payload)
  } finally {
    draftLoading.value = false
  }
}

async function loadPage() {
  pageLoading.value = true
  try {
    const shiftPayload = await fetchCurrentShift()
    currentShift.value = shiftPayload || {}
    equipmentOptions.value = shiftPayload?.workshop_id
      ? await fetchEquipment({ workshop_id: shiftPayload.workshop_id })
      : []

    if (shiftPayload?.attendance_machine_id) {
      machineId.value = shiftPayload.attendance_machine_id
    } else if (equipmentOptions.value.length === 1) {
      machineId.value = equipmentOptions.value[0].id
    } else if (!machineId.value && equipmentOptions.value.length > 0) {
      machineId.value = equipmentOptions.value[0].id
    }

    await loadDraft()
  } finally {
    pageLoading.value = false
  }
}

async function submit() {
  if (submitting.value) return
  if (isWithinSubmitCooldown(lastSubmitTime.value)) return
  if (submitDisabled.value) return
  submitting.value = true
  try {
    const requestBody = {
      machine_id: machineId.value,
      shift_id: currentShift.value.shift_id,
      business_date: currentShift.value.business_date,
      items: rows.value.map((row) => ({
        employee_id: row.employee_id,
        leader_status: row.leader_status,
        override_reason: String(row.override_reason || '').trim() || null,
        notes: String(row.notes || '').trim() || null
      }))
    }
    const payload = await submitAttendanceConfirmation(requestBody, { skipErrorToast: true })
    normalizeDraft(payload)
    currentShift.value = {
      ...currentShift.value,
      attendance_status: Number(payload.items?.filter((item) => item.is_anomaly).length || 0) > 0 ? 'pending' : 'confirmed',
      attendance_exception_count: Number(payload.items?.filter((item) => item.is_anomaly).length || 0),
      attendance_pending_count: 0,
      attendance_machine_id: payload.machine_id,
      attendance_machine_name: payload.machine_name
    }
    startSubmitCooldown()
    ElMessage.success('考勤确认已提交')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      await enqueuePendingRequest({
        type: 'http',
        method: 'post',
        url: '/attendance/confirm',
        dedupeKey: `attendance-confirm:${machineId.value || 0}:${currentShift.value.shift_id || 0}:${currentShift.value.business_date || ''}`,
        body: {
          machine_id: machineId.value,
          shift_id: currentShift.value.shift_id,
          business_date: currentShift.value.business_date,
          items: rows.value.map((row) => ({
            employee_id: row.employee_id,
            leader_status: row.leader_status,
            override_reason: String(row.override_reason || '').trim() || null,
            notes: String(row.notes || '').trim() || null
          }))
        }
      })
      startSubmitCooldown()
      ElMessage.success('已加入待同步队列，联网后自动同步')
      return
    }
    ElMessage.error(requestErrorMessage(error, '考勤确认提交失败'))
  } finally {
    submitting.value = false
  }
}

function goEntry() {
  router.push({ name: 'mobile-entry' })
}

watch(machineId, async (value, previous) => {
  if (!value || value === previous) return
  await loadDraft()
})

onMounted(loadPage)

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
})
</script>
