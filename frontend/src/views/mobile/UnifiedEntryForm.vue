<template>
  <div class="unified-entry" data-testid="unified-entry">
    <header class="ue-identity" :style="{ '--role-color': roleColor }">
      <div class="ue-identity__main">
        <strong>{{ roleLabel }}</strong>
        <span>{{ identityMeta }}</span>
      </div>
    </header>

    <div v-if="loading" class="ue-loading">加载中…</div>
    <div v-else-if="error" class="ue-error">{{ error }}</div>

    <template v-else>
      <div v-if="mode === 'per_coil'" class="ue-coil-header">
        <strong class="ue-coil-seq">第{{ coilSeq }}卷</strong>
        <span class="ue-coil-shift">{{ shiftName }} · 已录{{ history.length }}卷</span>
      </div>
      <div v-else-if="mode === 'owner_daily'" class="ue-person-header">
        <strong>{{ auth.displayName || roleLabel }}</strong>
        <span>{{ businessDate }} · 每日一录</span>
      </div>

      <div v-if="mode === 'per_coil' && canScan" class="ue-scan-row">
        <button class="ue-scan-btn" :disabled="scanning" @click="handleScanLookup()">
          {{ scanning ? '扫码中…' : '扫码带出' }}
        </button>
      </div>

      <section v-for="(group, gi) in groups" :key="gi" class="ue-group">
        <h3 class="ue-group__title">{{ group.label }}</h3>
        <div class="ue-fields">
          <div
            v-for="field in group.fields"
            :key="field.name"
            class="ue-field"
            :class="{
              'ue-field--wide': isWideField(field),
              'ue-field--spec': field.type === 'spec'
            }"
            :data-testid="`field-${field.name}`"
          >
            <label class="ue-field__label">
              <span v-if="field.required" class="mobile-required">*</span>
              {{ field.label }}
              <span v-if="field.unit" class="ue-field__unit">{{ field.unit }}</span>
            </label>
            <el-select
              v-if="field.type === 'select'"
              v-model="form[field.name]"
              filterable
              allow-create
              default-first-option
              :placeholder="field.hint || '选择或输入'"
              :aria-label="field.label"
              :disabled="isLockedField(field.name)"
              class="ue-el-select"
            >
              <el-option v-for="opt in resolveFieldOptions(field)" :key="opt.value ?? opt" :label="opt.label ?? opt" :value="opt.value ?? opt" />
            </el-select>
            <div v-else-if="field.type === 'spec'" class="ue-spec-row">
              <input
                v-model="specParts[field.name + '_0']"
                type="text"
                inputmode="decimal"
                class="ue-input ue-spec-input"
                placeholder="厚"
                :aria-label="`${field.label} 厚`"
                :disabled="isLockedField(field.name)"
                @input="syncSpec(field)"
              />
              <span class="ue-spec-sep">×</span>
              <input
                v-model="specParts[field.name + '_1']"
                type="text"
                inputmode="decimal"
                class="ue-input ue-spec-input"
                placeholder="宽"
                :aria-label="`${field.label} 宽`"
                :disabled="isLockedField(field.name)"
                @input="syncSpec(field)"
              />
              <span class="ue-spec-sep">×</span>
              <input
                v-if="!field.spec_suffix"
                v-model="specParts[field.name + '_2']"
                type="text"
                class="ue-input ue-spec-input"
                placeholder="长/C"
                :aria-label="`${field.label} 长`"
                :disabled="isLockedField(field.name)"
                @input="syncSpec(field)"
              />
              <span v-else class="ue-input ue-spec-input ue-spec-fixed">{{ field.spec_suffix }}</span>
            </div>
            <input
              v-else-if="field.type === 'number'"
              v-model.number="form[field.name]"
              type="number"
              inputmode="decimal"
              step="any"
              class="ue-input ue-input--number"
              :aria-label="field.label"
              :placeholder="field.hint || field.label"
              :disabled="isLockedField(field.name)"
            />
            <input
              v-else-if="field.type === 'time'"
              v-model="form[field.name]"
              type="time"
              class="ue-input"
              :aria-label="field.label"
              :disabled="isLockedField(field.name)"
            />
            <textarea
              v-else-if="field.type === 'textarea'"
              v-model="form[field.name]"
              class="ue-input ue-input--textarea"
              rows="2"
              :aria-label="field.label"
              :placeholder="field.hint || field.label"
              :disabled="isLockedField(field.name)"
            />
            <input
              v-else
              v-model="form[field.name]"
              type="text"
              class="ue-input"
              :aria-label="field.label"
              :placeholder="field.hint || field.label"
              :disabled="isLockedField(field.name)"
            />
          </div>
        </div>
      </section>

      <section v-if="visibleReadonlyFields.length" class="ue-group ue-group--readonly">
        <h3 class="ue-group__title">自动计算</h3>
        <div class="ue-readonly-row">
          <div v-for="rf in visibleReadonlyFields" :key="rf.name" class="ue-readonly-item">
            <span class="ue-readonly-item__label">{{ rf.label }}</span>
            <strong class="ue-readonly-item__value">{{ computeReadonly(rf) }}</strong>
          </div>
        </div>
      </section>

      <section v-if="showQualityModule" class="ue-group" data-testid="quality-module">
        <h3 class="ue-group__title">填报问题</h3>
        <div class="ue-fields">
          <div class="ue-field">
            <label class="ue-field__label">有填报问题</label>
            <el-switch v-model="quality.has_issue" />
          </div>
          <template v-if="quality.has_issue">
            <div class="ue-field">
              <label class="ue-field__label">问题类型</label>
              <el-select v-model="quality.issue_type" placeholder="选择类型">
                <el-option label="外观" value="外观" />
                <el-option label="尺寸" value="尺寸" />
                <el-option label="性能" value="性能" />
                <el-option label="包装" value="包装" />
                <el-option label="其他" value="其他" />
              </el-select>
            </div>
            <div class="ue-field">
              <label class="ue-field__label">问题描述</label>
              <textarea
                v-model="quality.issue_note"
                class="ue-input ue-input--textarea"
                rows="2"
                placeholder="简述发现的质量问题"
              />
            </div>
            <div class="ue-field">
              <label class="ue-field__label">现场照片</label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                @change="handleQualityPhoto"
              />
              <span v-if="quality.photo_name" class="ue-readonly-item__label">已选：{{ quality.photo_name }}</span>
            </div>
          </template>
        </div>
      </section>

      <div class="ue-actions">
        <button class="ue-submit" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中…' : submitButtonText }}
        </button>
        <button
          v-if="mode === 'per_coil' && lastCoilData"
          class="ue-split-btn"
          :disabled="submitting"
          @click="handleSplitCoil"
        >
          本卷分切（一坯两规格）
        </button>
      </div>

      <section v-if="history.length" class="ue-group">
        <h3 class="ue-group__title">{{ historyTitle }}</h3>
        <div class="ue-history">
          <div v-for="(item, i) in history" :key="i" class="ue-history-item">
            <span class="ue-history-item__index">{{ mode === 'per_coil' ? `第${item.seq || history.length - i}卷` : `#${i + 1}` }}</span>
            <span class="ue-history-item__summary">{{ summarize(item) }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { useAuthStore } from '../../stores/auth.js'
import {
  fetchCurrentShift,
  fetchEntryFields,
  saveMobileReport,
  submitMobileReport,
  fetchMobileReport,
  fetchCoilList,
  createCoilEntry,
  fetchFieldOptions,
  fetchOwnerDailyEntry,
  saveOwnerDailyEntry,
} from '../../api/mobile.js'
import { isEmptyValue, toNumber as normalizeNumberValue } from '../../utils/fieldValueHelpers.js'
import { computeReadonlyValue } from '../../utils/unifiedEntryHelpers.js'
import { validateEntryWeights } from '../../utils/entryWeightValidation.js'
import { requestErrorMessage } from '../../utils/reportStatus.js'
import { useScanLookup } from '../../composables/useScanLookup.js'
import { warnIfMachineMismatch } from '../../composables/useMachineMismatch.js'

const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const form = reactive({})
const specParts = reactive({})
const lockedFieldsSnapshot = ref({})
const lockedFieldsToken = ref('')
const groups = ref([])
const readonlyFields = ref([])
const visibleReadonlyFields = computed(() =>
  readonlyFields.value.filter((rf) => !rf.hidden)
)
const mode = ref('per_shift')
const submitTarget = ref('shift_report')
const identityField = ref(null)
const history = ref([])
const coilSeq = ref(1)
const lastCoilData = ref(null)
const { canScan, scanning, scan, scanLookup } = useScanLookup()

const shiftContext = ref(null)
const workshopName = computed(() => shiftContext.value?.workshop_name || '')
const shiftName = computed(() => shiftContext.value?.shift_name || '')
const businessDate = computed(() => shiftContext.value?.business_date || '')
const identityMeta = computed(() => {
  if (mode.value === 'owner_daily') return `${workshopName.value} · ${businessDate.value}`
  return `${workshopName.value} · ${shiftName.value} · ${businessDate.value}`
})
const roleLabel = computed(() => {
  const labels = {
    machine_operator: '主操',
    energy_stat: '车间电工',
    consumable_stat: '生产内勤',
    quality_owner: '全厂质检内勤',
    planning_owner: '全厂计划内勤',
    energy_chief: '全厂总电工',
    storage_owner: '成品库内勤',
    shipment_outflow_owner: '园区剪切内勤',
    recovery_owner: '回收内勤',
    overhaul_owner: '大修内勤',
  }
  return labels[auth.role] || auth.displayName
})

const ROLE_COLORS = {
  machine_operator: 'oklch(51% 0.17 255)',
  energy_stat: 'oklch(52% 0.13 158)',
  consumable_stat: 'oklch(54% 0.095 54)',
  quality_owner: 'oklch(55% 0.15 28)',
  planning_owner: 'oklch(51% 0.17 255)',
  energy_chief: 'oklch(52% 0.13 158)',
  storage_owner: 'oklch(54% 0.095 54)',
  shipment_outflow_owner: 'oklch(52% 0.13 158)',
  recovery_owner: 'oklch(50% 0.15 252)',
  overhaul_owner: 'oklch(52% 0.13 158)',
}
const roleColor = computed(() => ROLE_COLORS[auth.role] || 'oklch(51% 0.17 255)')

const dynamicOptionsMap = reactive({})

const quality = reactive({
  has_issue: false,
  issue_type: '',
  issue_note: '',
  photo_name: '',
  photo_data_url: '',
})
const showQualityModule = computed(() => mode.value === 'per_coil' && auth.role === 'machine_operator')
const COIL_DIRECT_FIELDS = new Set([
  'tracking_card_no',
  'alloy_grade',
  'input_spec',
  'output_spec',
  'on_machine_time',
  'off_machine_time',
  'input_weight',
  'output_weight',
  'unit_output',
  'scrap_weight',
  'material_state',
  'spool_weight',
  'operator_name',
  'operator_notes',
])
const QUALITY_TEMPLATE_FIELDS = new Set([
  'quality_note',
  'quality_issue_type',
  'quality_issue_card_no',
  'quality_issue_desc',
  'quality_issue_photo_path',
])
const submitButtonText = computed(() => {
  if (mode.value === 'per_coil') return '录入本卷'
  if (mode.value === 'owner_daily') return `提交 ${businessDate.value || '每日一录'}`
  return '提交'
})
const historyTitle = computed(() => {
  if (mode.value === 'per_coil') return `本班已录 (${history.value.length}卷)`
  if (mode.value === 'owner_daily') return `${businessDate.value || '本日'} 已录`
  return `本班已录 (${history.value.length})`
})

function resetQuality() {
  quality.has_issue = false
  quality.issue_type = ''
  quality.issue_note = ''
  quality.photo_name = ''
  quality.photo_data_url = ''
}

function handleQualityPhoto(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > 4 * 1024 * 1024) {
    ElMessage.warning('图片需小于 4MB')
    event.target.value = ''
    return
  }
  quality.photo_name = file.name
  const reader = new FileReader()
  reader.onload = () => { quality.photo_data_url = String(reader.result || '') }
  reader.readAsDataURL(file)
}

function buildQualityPayload() {
  if (!quality.has_issue) return null
  return {
    has_issue: true,
    issue_type: quality.issue_type || '',
    issue_note: quality.issue_note || '',
    photo_name: quality.photo_name || '',
    photo_data_url: quality.photo_data_url || '',
  }
}

function hasPayloadValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.length > 0
  return true
}

function appendTemplateExtraFields(extra, values) {
  for (const [key, value] of Object.entries(values)) {
    if (COIL_DIRECT_FIELDS.has(key) || QUALITY_TEMPLATE_FIELDS.has(key) || !hasPayloadValue(value)) continue
    extra[key] = value
  }
}

function resolveFieldOptions(field) {
  if (field.options) return field.options
  return dynamicOptionsMap[field.options_source] || []
}

function isWideField(field) {
  return field.type === 'textarea' || field.type === 'spec'
}

async function loadDynamicOptions(fields) {
  const sources = new Set()
  for (const f of fields) {
    if (f.type === 'select' && f.options_source && !f.options) sources.add(f.options_source)
  }
  for (const src of sources) {
    if (dynamicOptionsMap[src]) continue
    try {
      dynamicOptionsMap[src] = await fetchFieldOptions(src)
    } catch { /* ignore */ }
  }
}

function computeReadonly(rf) {
  return computeReadonlyValue(rf.compute, form, rf.unit)
}

function syncSpec(field) {
  const p0 = specParts[field.name + '_0'] || ''
  const p1 = specParts[field.name + '_1'] || ''
  // If field has spec_suffix, only include p0 and p1 in form value (for locked field validation)
  // The suffix is display-only and should not be part of the submitted value
  if (field.spec_suffix) {
    form[field.name] = [p0, p1].filter(Boolean).join('×')
  } else {
    const p2 = specParts[field.name + '_2'] || ''
    form[field.name] = [p0, p1, p2].filter(Boolean).join('×')
  }
}

function isLockedField(name) {
  return Object.prototype.hasOwnProperty.call(lockedFieldsSnapshot.value, name)
}

function currentLockValue(key) {
  if (key in form) return form[key]
  return undefined
}

function applyLockedSnapshot(lockKeys = []) {
  const snapshot = {}
  for (const key of lockKeys) {
    const value = currentLockValue(key)
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      snapshot[key] = value
    }
  }
  lockedFieldsSnapshot.value = snapshot
}

function applyScanLookupResult(result) {
  const fields = result?.header_fields || {}
  const mapped = {
    tracking_card_no: fields.tracking_card_no,
    alloy_grade: fields.alloy_grade,
    input_spec: fields.input_spec || fields.spec_display,
  }
  for (const [key, value] of Object.entries(mapped)) {
    if (value !== undefined && value !== null && key in form) {
      form[key] = value
    }
  }
  for (const g of groups.value) {
    for (const f of g.fields) {
      if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
    }
  }
  applyLockedSnapshot(result?.lock_keys || [])
  lockedFieldsToken.value = result?.lock_token || ''
}

async function handleScanLookup(qr) {
  try {
    const result = qr ? await scanLookup(qr) : await scan()
    if (!result) return
    applyScanLookupResult(result)
    warnIfMachineMismatch(result, auth)
    ElMessage.success(result.source === 'machine_identity' ? '已识别机台' : '已带出卷头字段')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '扫码失败')
  }
}

function normalizedFormValues() {
  const values = {}
  for (const group of groups.value) {
    for (const field of group.fields) {
      const value = form[field.name]
      values[field.name] = field.type === 'number' ? normalizeNumberValue(value) : value
    }
  }
  return values
}

function validateVisibleRequiredFields() {
  for (const group of groups.value) {
    for (const field of group.fields) {
      if (field.required && isEmptyValue(form[field.name])) {
        ElMessage.warning(`请先填写：${field.label}`)
        return false
      }
    }
  }
  return true
}

function validateBusinessRules() {
  const visibleFields = groups.value.flatMap((group) => group.fields || [])
  const message = validateEntryWeights(form, visibleFields)
  if (message) {
    ElMessage.warning(message)
    return false
  }
  return true
}

function buildCoilEntryPayload(sc) {
  const values = normalizedFormValues()
  const trackingKey = identityField.value || 'tracking_card_no'
  const trackingCardNo = String(values[trackingKey] || '').trim()
  const outputWeight = values.output_weight ?? values.unit_output
  const qualityPayload = buildQualityPayload()
  const extra = {}
  appendTemplateExtraFields(extra, values)
  if (qualityPayload) extra.quality_issue = qualityPayload
  return {
    tracking_card_no: trackingCardNo,
    alloy_grade: values.alloy_grade || null,
    input_spec: values.input_spec || values.ingot_spec || null,
    output_spec: values.output_spec || null,
    on_machine_time: values.on_machine_time || null,
    off_machine_time: values.off_machine_time || null,
    input_weight: values.input_weight,
    output_weight: outputWeight,
    scrap_weight: values.scrap_weight,
    material_state: values.material_state || null,
    spool_weight: values.spool_weight,
    operator_name: values.operator_name || auth.displayName || '',
    operator_notes: values.operator_notes || '',
    business_date: sc.business_date,
    shift_id: sc.shift_id,
    locked_fields_snapshot: lockedFieldsSnapshot.value,
    locked_fields_token: lockedFieldsToken.value,
    extra_payload: Object.keys(extra).length ? extra : null,
  }
}

function buildMobileReportPayload(sc) {
  const values = normalizedFormValues()
  const electricityDaily = values.electricity_daily ?? values.energy_kwh
  const gasDaily = values.gas_daily ?? values.gas_m3
  return {
    business_date: sc.business_date,
    shift_id: sc.shift_id,
    attendance_count: normalizeNumberValue(values.attendance_count),
    input_weight: normalizeNumberValue(values.input_weight),
    output_weight: normalizeNumberValue(values.output_weight),
    scrap_weight: normalizeNumberValue(values.scrap_weight),
    storage_prepared: normalizeNumberValue(values.storage_prepared),
    storage_finished: normalizeNumberValue(values.storage_finished),
    shipment_weight: normalizeNumberValue(values.shipment_weight),
    contract_received: normalizeNumberValue(values.contract_received),
    electricity_daily: normalizeNumberValue(electricityDaily),
    gas_daily: normalizeNumberValue(gasDaily),
    has_exception: Boolean(values.has_exception),
    exception_type: values.exception_type || null,
    note: values.operator_notes || values.energy_note || values.note || null,
  }
}

function buildOwnerDailyPayload(sc) {
  return {
    business_date: sc.business_date || dayjs().format('YYYY-MM-DD'),
    data: normalizedFormValues(),
  }
}

function initSpecParts(fieldName, value, suffix) {
  const parts = (value || '').split(/[×xX*]/)
  specParts[fieldName + '_0'] = parts[0] || ''
  specParts[fieldName + '_1'] = parts[1] || ''
  if (!suffix) specParts[fieldName + '_2'] = parts[2] || ''
}

function summarize(item) {
  const d = item.data || item
  const parts = []
  if (d.alloy_grade) parts.push(d.alloy_grade)
  if (d.input_weight) parts.push(d.input_weight + '→')
  if (d.output_weight) parts.push(d.output_weight)
  if (d.energy_kwh) parts.push(d.energy_kwh + 'kWh')
  if (d.downtime_minutes) parts.push(d.downtime_minutes + 'min')
  return parts.join(' ') || JSON.stringify(d).slice(0, 40)
}

function handleSplitCoil() {
  if (!lastCoilData.value) return
  const prev = lastCoilData.value
  for (const key of Object.keys(form)) {
    if (key === 'output_weight' || key === 'output_spec') {
      form[key] = typeof form[key] === 'number' ? null : ''
    } else if (key in prev) {
      form[key] = prev[key]
    }
  }
  for (const g of groups.value) {
    for (const f of g.fields) {
      if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
    }
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [shift, fields] = await Promise.all([fetchCurrentShift(), fetchEntryFields()])
    shiftContext.value = shift
    if (fields.error) {
      error.value = fields.error
      return
    }
    groups.value = fields.groups || []
    readonlyFields.value = fields.readonly_fields || []
    mode.value = fields.mode || 'per_shift'
    submitTarget.value = fields.submit_target || (fields.mode === 'per_coil' ? 'coil_entry' : 'shift_report')
    identityField.value = fields.identity_field || null
    if (!shift.shift_id && mode.value !== 'owner_daily') {
      error.value = '未找到当前班次，请联系管理员配置班次。'
      return
    }

    for (const g of groups.value) {
      for (const f of g.fields) {
        if (!(f.name in form)) form[f.name] = f.type === 'number' ? null : ''
        if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
      }
    }

    const allFields = groups.value.flatMap(g => g.fields)
    loadDynamicOptions(allFields)

    if (shift.report_id && mode.value === 'per_shift') {
      try {
        const report = await fetchMobileReport(shift.business_date, shift.shift_id)
        if (report?.data) {
          for (const [k, v] of Object.entries(report.data)) {
            if (k in form && v != null) form[k] = v
          }
        }
      } catch { /* first time, no report yet */ }
    }

    if (mode.value === 'owner_daily') {
      try {
        const existing = await fetchOwnerDailyEntry(shift.business_date)
        if (existing?.data) {
          for (const [k, v] of Object.entries(existing.data)) {
            if (k in form && v != null) form[k] = v
          }
          history.value = [existing]
        }
      } catch { /* first time, no daily owner row yet */ }
    }

    if (mode.value === 'per_coil') {
      try {
        const coils = await fetchCoilList(shift.business_date, shift.shift_id)
        history.value = Array.isArray(coils) ? coils : []
        coilSeq.value = history.value.length + 1
      } catch { /* no coils yet */ }
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (submitting.value) return
  const sc = shiftContext.value
  if (!sc || (submitTarget.value !== 'owner_daily' && !sc.shift_id)) return
  if (!validateVisibleRequiredFields()) return
  if (!validateBusinessRules()) return

  submitting.value = true
  try {
    if (submitTarget.value === 'coil_entry') {
      const saved = await createCoilEntry(buildCoilEntryPayload(sc), { skipErrorToast: true })
      ElMessage.success(`第${coilSeq.value}卷 录入成功`)
      lastCoilData.value = { ...form }
      history.value.unshift(saved?.data ? saved : { seq: coilSeq.value, ...form })
      coilSeq.value++
      for (const key of Object.keys(form)) {
        form[key] = typeof form[key] === 'number' ? null : ''
      }
      lockedFieldsSnapshot.value = {}
      lockedFieldsToken.value = ''
      resetQuality()
    } else if (submitTarget.value === 'owner_daily') {
      const saved = await saveOwnerDailyEntry(buildOwnerDailyPayload(sc), { skipErrorToast: true })
      ElMessage.success('提交成功')
      history.value = saved ? [saved] : []
    } else {
      const payload = buildMobileReportPayload(sc)
      await saveMobileReport(payload)
      await submitMobileReport(payload)
      ElMessage.success('提交成功')
    }
  } catch (e) {
    ElMessage.error(requestErrorMessage(e, '提交失败'))
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.unified-entry {
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 920px;
  margin: 0 auto;
  background: transparent;
  color: var(--xt-text);
  padding-bottom: calc(32px + env(safe-area-inset-bottom, 0px));
}

.ue-identity {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background:
    linear-gradient(135deg, rgba(0, 242, 255, 0.14), rgba(4, 16, 31, 0.92)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent);
  border-bottom: 1px solid rgba(0, 242, 255, 0.18);
  border-left: 3px solid var(--role-color);
  color: var(--xt-text-inverse);
  box-shadow: 0 16px 34px rgba(0, 0, 0, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(14px);
}

.ue-identity__main strong {
  display: block;
  font-size: 20px;
  font-weight: 850;
  line-height: 1.18;
  letter-spacing: -0.012em;
  color: var(--xt-text);
  text-shadow: 0 0 20px rgba(0, 242, 255, 0.18);
}

.ue-identity__main span {
  font-size: 13px;
  color: var(--xt-text-secondary);
  opacity: 1;
}

.ue-loading, .ue-error {
  padding: 48px 16px;
  text-align: center;
  color: var(--xt-text-secondary);
  font-size: 15px;
}

.ue-error { color: var(--xt-danger); }

.ue-coil-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 16px 16px 0;
}

.ue-coil-seq {
  font-family: var(--xt-font-number);
  font-size: 28px;
  font-weight: 950;
  letter-spacing: -0.02em;
  color: var(--xt-primary);
  text-shadow: 0 0 20px rgba(0, 242, 255, 0.18);
}

.ue-coil-shift {
  font-size: 13px;
  color: var(--xt-text-muted);
}

.ue-person-header {
  display: grid;
  gap: 4px;
  margin: 16px 16px 0;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--role-color), transparent 68%);
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--role-color), transparent 86%), rgba(5, 14, 28, 0.78)),
    radial-gradient(circle at 12% 0%, rgba(0, 242, 255, 0.1), transparent 48%);
  box-shadow: 0 16px 34px rgba(0, 0, 0, 0.22);
}

.ue-person-header strong {
  font-size: 20px;
  font-weight: 900;
  color: var(--xt-text);
}

.ue-person-header span {
  font-size: 13px;
  color: var(--xt-text-secondary);
}

.ue-scan-row {
  padding: 12px 16px 0;
}

.ue-scan-btn {
  width: 100%;
  min-height: 44px;
  border: 1px solid var(--xt-primary);
  border-radius: 10px;
  background: rgba(0, 242, 255, 0.08);
  color: var(--xt-primary);
  font-size: 15px;
  font-weight: 800;
}

.ue-scan-btn:active {
  transform: scale(0.98);
}

.ue-group {
  margin: 12px 16px 0;
}

.ue-group__title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--xt-text-secondary);
  margin: 0 0 8px;
  text-transform: uppercase;
}

.ue-fields {
  display: grid;
  grid-template-columns: 1fr;
  background:
    linear-gradient(145deg, rgba(10, 29, 52, 0.86), rgba(4, 13, 26, 0.76)),
    radial-gradient(circle at 10% 0%, rgba(0, 242, 255, 0.08), transparent 42%);
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: var(--xt-radius-xl);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  padding: 4px 16px;
}

.ue-field {
  padding: 12px 0;
  border-bottom: 1px solid rgba(0, 242, 255, 0.1);
  min-width: 0;
}

.ue-field:last-child { border-bottom: none; }

.ue-field__label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--xt-text);
  margin-bottom: 6px;
}

.mobile-required {
  color: var(--xt-danger);
}

.ue-field__unit {
  font-size: 12px;
  font-weight: 400;
  color: var(--xt-text-muted);
}

.ue-input {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 8px 12px;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 8px;
  font-size: 16px;
  font-family: inherit;
  background: rgba(2, 9, 18, 0.68);
  color: var(--xt-text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
  -webkit-appearance: none;
}

.ue-input:focus {
  border-color: var(--xt-primary);
  box-shadow: var(--app-focus-ring), inset 0 -1px 0 rgba(0, 242, 255, 0.5);
}

.ue-input--number {
  text-align: right;
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

.ue-input--select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 5l3 3 3-3' fill='none' stroke='%23999' stroke-width='1.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.ue-input--textarea {
  min-height: 64px;
  resize: vertical;
}

.ue-group--readonly {
  margin-top: 8px;
}

.ue-readonly-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.ue-readonly-item {
  flex: 1;
  min-width: 100px;
  background: rgba(3, 12, 24, 0.62);
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  padding: 12px;
  box-shadow: none;
}

.ue-readonly-item__label {
  display: block;
  font-size: 12px;
  color: var(--xt-text-muted);
  margin-bottom: 4px;
}

.ue-readonly-item__value {
  font-family: var(--xt-font-number);
  font-size: 20px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.012em;
}

.ue-actions {
  position: sticky;
  bottom: calc(var(--xt-tabbar-height, 64px) + env(safe-area-inset-bottom, 0px) + 8px);
  z-index: 9;
  margin: 16px;
  padding: 10px;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: var(--xt-radius-xl);
  background: linear-gradient(180deg, rgba(5, 15, 28, 0.92), rgba(3, 10, 20, 0.96));
  box-shadow: 0 -12px 34px rgba(0, 0, 0, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(14px);
}

.ue-submit {
  position: relative;
  overflow: hidden;
  display: block;
  width: 100%;
  min-height: 48px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #00f2ff, #74f5ff);
  color: #001d22;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
  transition: transform 0.1s, box-shadow 0.15s;
}

.ue-submit:active { transform: scale(0.96); }
.ue-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.ue-submit::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.32), transparent);
  transform: translateX(-110%);
  animation: ueSubmitSweep 4.4s ease-in-out infinite;
}

.ue-split-btn {
  display: block;
  width: 100%;
  min-height: 44px;
  margin-top: 8px;
  border: 1.5px solid var(--xt-primary);
  border-radius: 10px;
  background: rgba(0, 242, 255, 0.06);
  color: var(--xt-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.ue-split-btn:active { background: var(--xt-primary-soft); }

.unified-entry :deep(.el-select__wrapper) {
  min-height: 48px;
  border: 1px solid rgba(0, 242, 255, 0.16);
  background: rgba(2, 9, 18, 0.68);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
}

.ue-spec-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ue-spec-input {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.ue-spec-sep {
  font-size: 16px;
  font-weight: 700;
  color: var(--xt-text-muted);
  flex-shrink: 0;
}

.ue-spec-fixed {
  background: rgba(0, 242, 255, 0.07);
  border-color: transparent;
  color: var(--xt-text-secondary);
  font-weight: 700;
  text-align: center;
  pointer-events: none;
}

.ue-history {
  background: linear-gradient(145deg, rgba(10, 29, 52, 0.86), rgba(4, 13, 26, 0.76));
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: var(--xt-radius-xl);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}

.ue-history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(0, 242, 255, 0.1);
  font-size: 14px;
}

.ue-history-item:last-child { border-bottom: none; }

.ue-history-item__index {
  font-family: var(--xt-font-number);
  font-weight: 700;
  color: var(--xt-text-muted);
  min-width: 28px;
}

.ue-history-item__summary {
  color: var(--xt-text);
}

@keyframes ueSubmitSweep {
  0%, 48% { transform: translateX(-110%); }
  100% { transform: translateX(110%); }
}

@media (min-width: 760px) {
  .ue-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 18px;
    padding: 8px 18px;
  }

  .ue-field {
    padding: 14px 0;
  }

  .ue-field--wide,
  .ue-field--spec {
    grid-column: 1 / -1;
  }

  .ue-actions {
    bottom: 18px;
  }
}
</style>
