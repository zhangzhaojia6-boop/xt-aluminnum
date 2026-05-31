<template>
  <div class="mobile-shell attendance-radar" data-testid="attendance-confirm">
    <div class="attendance-radar__hero mobile-top">
      <div class="attendance-radar__hero-copy">
        <span class="attendance-radar__eyebrow">ATTENDANCE RADAR</span>
        <h1>考勤确认</h1>
        <p>钉钉打卡 · 现场确认 · 人事复核</p>
      </div>
      <div class="attendance-radar__hero-side">
        <span class="attendance-radar__status" :class="attendanceStateTone">
          <i aria-hidden="true"></i>{{ attendanceStatusLabel }}
        </span>
        <div class="header-actions attendance-radar__actions">
          <el-button plain class="attendance-radar__button" @click="loadPage">刷新</el-button>
        </div>
      </div>
    </div>

    <el-alert
      v-if="pageError"
      class="panel attendance-radar__alert"
      type="error"
      :closable="false"
      show-icon
      :title="pageError"
    />

    <section class="attendance-radar__panel panel mobile-card">
      <header class="attendance-radar__panel-head">
        <div>
          <span class="attendance-radar__eyebrow">SHIFT SIGNAL</span>
          <strong>当前班次</strong>
        </div>
        <span class="attendance-radar__panel-chip">{{ currentShift.shift_id ? '在线' : '待载入' }}</span>
      </header>
      <div v-if="pageLoading" class="attendance-radar__state mobile-placeholder">
        <span class="attendance-radar__orbit" aria-hidden="true"></span>
        <strong>正在加载当前班次与机台...</strong>
      </div>
      <div v-else-if="!currentShift.shift_id" class="attendance-radar__state mobile-placeholder">
        <span class="attendance-radar__orbit is-muted" aria-hidden="true"></span>
        <strong>当前账号没有可确认的班次。</strong>
      </div>
      <div v-else class="attendance-radar__readouts mobile-overview-grid">
        <div class="attendance-radar__readout mobile-overview-item">
          <span>业务日期</span>
          <strong>{{ currentShift.business_date }}</strong>
        </div>
        <div class="attendance-radar__readout mobile-overview-item">
          <span>班次</span>
          <strong>{{ currentShift.shift_name || currentShift.shift_code || '-' }}</strong>
        </div>
        <div class="attendance-radar__readout mobile-overview-item">
          <span>车间</span>
          <strong>{{ currentShift.workshop_name || '-' }}</strong>
        </div>
        <div class="attendance-radar__readout mobile-overview-item">
          <span>当前状态</span>
          <strong>{{ attendanceStatusLabel }}</strong>
        </div>
        <div class="attendance-radar__readout mobile-overview-item">
          <span>应到</span>
          <strong>{{ headcount }}</strong>
        </div>
        <div class="attendance-radar__readout mobile-overview-item">
          <span>差异</span>
          <strong>{{ anomalyCount }}</strong>
        </div>
      </div>
    </section>

    <section v-if="currentShift.shift_id" class="attendance-radar__panel attendance-radar__panel--control panel mobile-card">
      <header class="attendance-radar__panel-head">
        <div>
          <span class="attendance-radar__eyebrow">CONTROL BAY</span>
          <strong>确认范围</strong>
        </div>
        <span class="attendance-radar__panel-chip">{{ selectedMachineName || '选择机台' }}</span>
      </header>
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
    </section>

    <el-alert
      v-if="!pageLoading && currentShift.shift_id && currentShift.attendance_exception_count"
      class="panel attendance-radar__alert"
      type="warning"
      :closable="false"
      show-icon
      :title="`本班已存在 ${currentShift.attendance_exception_count} 条考勤差异，提交后会进入人事复核。`"
    />

    <section v-if="currentShift.shift_id && machineId" class="attendance-radar__panel attendance-radar__ledger panel mobile-card">
      <header class="attendance-radar__panel-head">
        <div class="mobile-attendance-header">
          <div>
            <span class="attendance-radar__eyebrow">PERSONNEL TRACE</span>
            <strong>{{ selectedMachineName || '机台' }}</strong>
            <span>{{ currentShift.shift_name || currentShift.shift_code || '-' }}</span>
            <span>{{ currentShift.business_date }}</span>
          </div>
          <el-tag :type="locked ? 'success' : 'warning'" effect="light" class="attendance-radar__tag">
            {{ locked ? '已确认' : '待确认' }}
          </el-tag>
        </div>
      </header>

      <div v-if="draftLoading" class="attendance-radar__state mobile-placeholder">
        <span class="attendance-radar__orbit" aria-hidden="true"></span>
        <strong>正在加载钉钉打卡与班组名单...</strong>
      </div>
      <el-empty
        v-else-if="!rows.length"
        description="当前机台没有班组名单或打卡草稿，请先确认排班和钉钉同步。"
      />
      <div v-else class="mobile-attendance-list">
        <section
          v-for="(row, index) in rows"
          :key="row.employee_id"
          :class="['attendance-radar__person mobile-attendance-card', attendanceToneClass(row), { 'is-anomaly': isAnomaly(row) }]"
          :style="{ '--attendance-index': index }"
        >
          <div class="attendance-radar__person-head">
            <span class="attendance-radar__status" :class="attendanceToneClass(row)">
              <i aria-hidden="true"></i>{{ isAnomaly(row) ? '异常待核' : '打卡正常' }}
            </span>
            <span class="attendance-radar__seq">LOG {{ attendanceSeq(index) }}</span>
          </div>
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
              placeholder="现场负责人修改自动判定时必须说明原因"
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
    </section>

    <div class="attendance-radar__dock mobile-sticky-actions">
      <el-button size="large" class="attendance-radar__button" @click="loadDraft" :disabled="!machineId" :loading="draftLoading">重新拉取</el-button>
      <el-button
        type="primary"
        size="large"
        class="attendance-radar__submit"
        :disabled="submitDisabled"
        :loading="submitting"
        @click="submit"
      >
        提交确认
      </el-button>
    </div>

  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchAttendanceDraft, submitAttendanceConfirmation } from '../../api/attendance'
import { isRetryableNetworkError, useRetryQueue } from '../../composables/useRetryQueue'
import { fetchEquipment } from '../../api/master'
import { fetchCurrentShift } from '../../api/mobile'
import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown } from '../../utils/submitGuard'

const { enqueuePendingRequest } = useRetryQueue()

const pageLoading = ref(true)
const draftLoading = ref(false)
const submitting = ref(false)
const pageError = ref('')
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
const anomalyCount = computed(() => {
  const rowCount = rows.value.filter((row) => isAnomaly(row)).length
  return Number(currentShift.value?.attendance_exception_count || rowCount || 0)
})
const selectedMachineName = computed(() => {
  return equipmentOptions.value.find((item) => item.id === machineId.value)?.name || currentShift.value.attendance_machine_name || ''
})
const attendanceStatusLabel = computed(() => {
  if (locked.value) return '已确认'
  if (Number(currentShift.value?.attendance_exception_count || 0) > 0) return '存在异常'
  if (currentShift.value?.attendance_status === 'not_started') return '未确认'
  return '待确认'
})
const attendanceStateTone = computed(() => {
  if (locked.value) return 'is-normal'
  if (anomalyCount.value > 0) return 'is-danger'
  if (currentShift.value?.attendance_status === 'not_started') return 'is-warning'
  return 'is-warning'
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
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
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

function attendanceSeq(index) {
  return String(index + 1).padStart(2, '0')
}

function attendanceToneClass(row) {
  if (isAnomaly(row)) return 'is-danger'
  if (['late', 'early_leave', 'absent'].includes(row?.leader_status)) return 'is-warning'
  return 'is-normal'
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
  } catch (error) {
    normalizeDraft({ status: 'draft', items: [] })
    ElMessage.error(requestErrorMessage(error, '加载考勤草稿失败，请稍后重试'))
  } finally {
    draftLoading.value = false
  }
}

async function loadPage() {
  pageLoading.value = true
  pageError.value = ''
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
  } catch (error) {
    pageError.value = requestErrorMessage(error, '加载考勤确认页面失败，请刷新重试。')
    currentShift.value = {}
    equipmentOptions.value = []
    machineId.value = null
    normalizeDraft({ status: 'draft', items: [] })
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

watch(machineId, async (value, previous) => {
  if (!value || value === previous) return
  await loadDraft()
})

onMounted(loadPage)

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
})
</script>

<style scoped>
.attendance-radar {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.attendance-radar::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    radial-gradient(circle at 16% 0%, rgba(0, 242, 255, 0.14), transparent 32%),
    radial-gradient(circle at 92% 18%, rgba(255, 171, 0, 0.1), transparent 24%),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.035) 0 1px, transparent 1px 28px),
    repeating-linear-gradient(0deg, transparent 0 18px, rgba(0, 242, 255, 0.035) 19px 20px);
  opacity: 0.72;
  transform: translateX(-50%);
}

.attendance-radar > * {
  position: relative;
  z-index: 1;
}

.attendance-radar__hero,
.attendance-radar__panel,
.attendance-radar__person,
.attendance-radar__dock {
  position: relative;
  overflow: hidden;
}

.attendance-radar__hero {
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
}

.attendance-radar__hero::after,
.attendance-radar__panel::after,
.attendance-radar__dock::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 0 38%, rgba(0, 242, 255, 0.12) 49%, transparent 60% 100%);
  opacity: 0;
  transform: translateX(-76%);
}

.attendance-radar__hero::after {
  animation: attendanceRadarScan 6.4s ease-in-out infinite;
}

.attendance-radar__hero-copy {
  min-width: 0;
}

.attendance-radar__hero-side {
  display: grid;
  gap: 10px;
}

.attendance-radar__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: rgba(0, 242, 255, 0.86);
  font-size: 10px;
  font-weight: 950;
  letter-spacing: 0.16em;
}

.attendance-radar__eyebrow::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.72);
}

.mobile-top h1,
.mobile-top p {
  writing-mode: horizontal-tb;
}

.mobile-top h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.mobile-top p {
  margin: 8px 0 0;
}

.attendance-radar__actions {
  width: 100%;
}

.attendance-radar__panel {
  padding: 12px;
  border-radius: 18px;
}

.attendance-radar__panel--control {
  border-color: rgba(0, 242, 255, 0.22);
}

.attendance-radar__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 14px;
}

.attendance-radar__panel-head strong {
  display: block;
  color: #e8fdff;
  font-size: 18px;
  font-weight: 950;
}

.attendance-radar__panel-chip,
.attendance-radar__seq {
  display: block;
  color: rgba(185, 218, 235, 0.68);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-align: right;
}

.attendance-radar__readouts {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.attendance-radar__readout {
  min-width: 0;
  border-color: rgba(0, 242, 255, 0.16);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent),
    rgba(2, 10, 22, 0.4);
}

.attendance-radar__readout strong {
  color: #e8fdff;
  font-variant-numeric: tabular-nums;
}

.attendance-radar__state {
  display: grid;
  place-items: center;
  min-height: 190px;
  gap: 8px;
  text-align: center;
}

.attendance-radar__state strong {
  color: #e8fdff;
  font-size: 16px;
}

.attendance-radar__orbit {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 1px solid rgba(0, 242, 255, 0.34);
  background:
    radial-gradient(circle, rgba(0, 242, 255, 0.2) 0 22%, transparent 23%),
    conic-gradient(from 120deg, rgba(0, 242, 255, 0.78), transparent 34%, rgba(255, 171, 0, 0.42), transparent 72%, rgba(0, 242, 255, 0.78));
  box-shadow: 0 0 38px rgba(0, 242, 255, 0.14);
  animation: attendanceRadarOrbit 5s linear infinite;
}

.attendance-radar__orbit.is-muted {
  opacity: 0.5;
}

.attendance-radar__alert {
  border-color: rgba(255, 171, 0, 0.24);
  background: rgba(28, 18, 4, 0.38);
}

.mobile-attendance-header {
  width: 100%;
  align-items: flex-start;
}

.mobile-attendance-header strong {
  color: #e8fdff;
  font-size: 18px;
  font-weight: 950;
}

.attendance-radar__tag {
  flex: 0 0 auto;
}

.attendance-radar__person {
  padding: 14px;
  border-radius: 16px;
  animation: attendanceRadarCardIn 420ms ease both;
  animation-delay: calc(var(--attendance-index) * 62ms);
}

.attendance-radar__person.is-danger {
  border-color: rgba(255, 92, 53, 0.32);
  box-shadow: inset 3px 0 0 rgba(255, 92, 53, 0.7), 0 0 24px rgba(255, 92, 53, 0.08);
}

.attendance-radar__person.is-warning {
  border-color: rgba(255, 171, 0, 0.3);
}

.attendance-radar__person-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.attendance-radar__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #dffbff;
  font-size: 11px;
  font-weight: 950;
  letter-spacing: 0.08em;
}

.attendance-radar__status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 0 4px rgba(0, 242, 255, 0.12), 0 0 18px rgba(0, 242, 255, 0.72);
  animation: attendanceRadarLed 1.8s ease-in-out infinite;
}

.attendance-radar__status.is-warning i {
  background: #ffab00;
  box-shadow: 0 0 0 4px rgba(255, 171, 0, 0.12), 0 0 18px rgba(255, 171, 0, 0.68);
}

.attendance-radar__status.is-danger i {
  background: #ff5c35;
  box-shadow: 0 0 0 4px rgba(255, 92, 53, 0.12), 0 0 18px rgba(255, 92, 53, 0.7);
}

.mobile-attendance-card__name {
  font-size: 20px;
  font-weight: 950;
  letter-spacing: -0.02em;
}

.mobile-attendance-card__clock,
.mobile-attendance-card__metrics {
  font-variant-numeric: tabular-nums;
}

.attendance-radar__dock {
  border: 1px solid rgba(0, 242, 255, 0.2);
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.08), rgba(3, 12, 24, 0.94)),
    rgba(3, 12, 24, 0.84);
  box-shadow: 0 -20px 50px rgba(0, 0, 0, 0.28);
}

.attendance-radar__button,
.attendance-radar__submit {
  position: relative;
  min-height: 44px;
  overflow: hidden;
}

.attendance-radar__button::after,
.attendance-radar__submit::after {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  opacity: 0;
  transform: translateX(-100%);
}

.attendance-radar__submit {
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.16);
}

.attendance-radar :deep(.el-select__wrapper),
.attendance-radar :deep(.el-textarea__inner) {
  border-color: rgba(0, 242, 255, 0.16);
  background: rgba(4, 14, 26, 0.74);
}

.attendance-radar :deep(.el-select__wrapper.is-focused),
.attendance-radar :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px rgba(0, 242, 255, 0.32), 0 0 18px rgba(0, 242, 255, 0.08);
}

@media (hover: hover) {
  .attendance-radar__button:hover::after,
  .attendance-radar__submit:hover::after {
    animation: attendanceRadarButtonSweep 620ms ease;
  }

  .attendance-radar__person:hover {
    border-color: rgba(0, 242, 255, 0.32);
  }
}

.attendance-radar__button:active,
.attendance-radar__submit:active {
  transform: scale(0.97);
}

@keyframes attendanceRadarScan {
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

@keyframes attendanceRadarButtonSweep {
  0% {
    opacity: 0;
    transform: translateX(-100%);
  }
  45% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateX(100%);
  }
}

@keyframes attendanceRadarCardIn {
  from {
    opacity: 0;
    transform: translate3d(0, 12px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes attendanceRadarLed {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes attendanceRadarOrbit {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 480px) {
  .attendance-radar__readouts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .attendance-radar__dock .el-button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .attendance-radar__hero::after,
  .attendance-radar__orbit,
  .attendance-radar__person,
  .attendance-radar__status i {
    animation: none;
  }
}
</style>
