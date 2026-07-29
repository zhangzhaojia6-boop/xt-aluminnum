<template>
  <div class="unified-entry" data-testid="unified-entry" data-visual-pass="stitch-image2-second-pass-mobile">
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
        <div class="ue-owner-date-control">
          <label for="owner-daily-business-date">业务日期</label>
          <select
            id="owner-daily-business-date"
            v-model="ownerDailySelectedDate"
            :disabled="ownerDailyLoading || submitting"
            @change="loadOwnerDailyEntryForDate"
          >
            <option v-for="dateOption in ownerDailyDateOptions" :key="dateOption" :value="dateOption">
              {{ dateOption }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="mode === 'per_coil' && canScan" class="ue-scan-row">
        <button class="ue-scan-btn" :disabled="scanning" @click="handleScanLookup()">
          {{ scanning ? '扫码中…' : '扫码带出' }}
        </button>
      </div>

      <section v-if="mesReferenceRows.length" class="ue-mes-reference" data-testid="mes-assisted-reference">
        <header>
          <strong>MES 参考值</strong>
          <span>人工填报值可改</span>
        </header>
        <div class="ue-mes-reference__grid">
          <article v-for="row in mesReferenceRows" :key="row.key">
            <span>{{ row.label }}</span>
            <b>MES {{ row.reference }}</b>
            <em>人工填报值 {{ row.manual }}</em>
          </article>
        </div>
      </section>

      <section v-for="(group, gi) in groups" :key="gi" class="ue-group">
        <h3 class="ue-group__title">{{ group.label }}</h3>
        <div class="ue-fields">
          <div
            v-for="field in group.fields"
            :key="field.name"
            class="ue-field"
            :class="{
              'ue-field--wide': isWideField(field),
              'ue-field--spec': field.type === 'spec',
              'ue-field--requested': requestedEntryFields.includes(field.name)
            }"
            :data-testid="`field-${field.name}`"
          >
            <label class="ue-field__label">
              <span v-if="field.required" class="mobile-required">*</span>
              {{ field.label }}
              <span v-if="field.unit" class="ue-field__unit">{{ field.unit }}</span>
            </label>
            <div v-if="field.type === 'machine_stop_list'" class="ue-machine-stops">
              <article
                v-for="(record, recordIndex) in machineStopRows(field.name)"
                :key="recordIndex"
                class="ue-machine-stop"
              >
                <div class="ue-machine-stop__heading">
                  <b>第 {{ recordIndex + 1 }} 条</b>
                  <button
                    type="button"
                    class="ue-icon-button"
                    :aria-label="`删除第 ${recordIndex + 1} 条停机记录`"
                    title="删除"
                    @click="removeMachineStopRecord(field.name, recordIndex)"
                  >
                    <Delete />
                  </button>
                </div>
                <div class="ue-machine-stop__grid">
                  <input v-model.trim="record.machine_name" class="ue-input" type="text" placeholder="机台，如 2号机" aria-label="机台" />
                  <input v-model.trim="record.workshop_name" class="ue-input" type="text" placeholder="车间" aria-label="车间" readonly />
                  <input v-model.trim="record.shift_name" class="ue-input" type="text" placeholder="班次" aria-label="班次" />
                  <input
                    v-model.number="record.downtime_minutes"
                    class="ue-input ue-input--number"
                    type="number"
                    inputmode="numeric"
                    min="1"
                    max="1440"
                    step="1"
                    placeholder="停机分钟"
                    aria-label="停机分钟"
                  />
                  <input v-model.trim="record.downtime_reason" class="ue-input ue-machine-stop__reason" type="text" placeholder="停机原因" aria-label="停机原因" />
                </div>
              </article>
              <button type="button" class="ue-add-record" @click="addMachineStopRecord(field.name)">
                <Plus />
                添加停机记录
              </button>
            </div>
            <el-select
              v-else-if="field.type === 'select'"
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

      <section v-if="showMachineEnergyDetails" class="ue-group ue-group--machine-energy" data-testid="machine-energy-details">
        <h3 class="ue-group__title">机列能耗明细</h3>
        <div class="ue-machine-energy-list">
          <div
            v-for="(rec, idx) in form.machine_energy_records"
            :key="rec.machine_id || rec.machine_code || idx"
            class="ue-machine-energy-row"
          >
            <div class="ue-machine-energy-name">{{ rec.machine_name || rec.machine_code || `机列${idx + 1}` }}</div>
            <div class="ue-machine-energy-fields">
              <label class="ue-machine-energy-field">
                <span>电耗</span>
                <input
                  v-model.number="rec.energy_kwh"
                  type="number"
                  inputmode="decimal"
                  step="any"
                  class="ue-input ue-input--number"
                  aria-label="机列电耗"
                  placeholder="kWh"
                />
              </label>
              <label class="ue-machine-energy-field">
                <span>气耗</span>
                <input
                  v-model.number="rec.gas_m3"
                  type="number"
                  inputmode="decimal"
                  step="any"
                  class="ue-input ue-input--number"
                  aria-label="机列气耗"
                  placeholder="m³"
                />
              </label>
            </div>
          </div>
          <div class="ue-machine-energy-total">
            <span>合计电耗：{{ machineEnergyTotalKwh }}</span>
            <span>合计气耗：{{ machineEnergyTotalGas }}</span>
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
        <button class="ue-submit" data-testid="unified-entry-submit" :disabled="submitting || ownerDailyLoading" @click="handleSubmit">
          {{ submitting ? '提交中…' : ownerDailyLoading ? '加载中…' : submitButtonText }}
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
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
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
import {
  inferOwnerDailyBusinessDate,
  ownerDailyBusinessDateOptions,
  resolveRecentRequestedBusinessDate,
  resolveRequestedEntryFields,
  resolveOwnerDailyRequestedBusinessDate,
} from '../../utils/shiftClock.js'
import { formatShiftLabel } from '../../utils/display.js'

const auth = useAuthStore()
const route = useRoute()

const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const ownerDailyLoading = ref(false)
const ownerDailySelectedDate = ref('')
const form = reactive({})
const specParts = reactive({})
const lockedFieldsSnapshot = ref({})
const lockedFieldsToken = ref('')
const mesReferenceFields = ref([])
const groups = ref([])
const requestedEntryFields = ref([])
const readonlyFields = ref([])
const entryRoleLabel = ref('')
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
const shiftName = computed(() => formatShiftLabel(shiftContext.value?.shift_name || shiftContext.value?.shift_code, ''))
const businessDate = computed(() => (
  mode.value === 'owner_daily'
    ? ownerDailySelectedDate.value || shiftContext.value?.business_date || ''
    : shiftContext.value?.business_date || ''
))
const ownerDailyDateOptions = computed(() => ownerDailyBusinessDateOptions(
  shiftContext.value?.business_date || inferOwnerDailyBusinessDate()
))
const workshopMachines = computed(() =>
  Array.isArray(shiftContext.value?.workshop_machines) ? shiftContext.value.workshop_machines : []
)
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
  return entryRoleLabel.value || labels[auth.role] || auth.displayName
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
  'trim_weight',
  'tray_weight',
  'operator_name',
  'operator_notes',
])
const MES_ASSISTED_SCAN_FIELDS = [
  'tracking_card_no',
  'alloy_grade',
  'input_spec',
  'output_spec',
  'input_weight',
  'output_weight',
  'on_machine_time',
  'off_machine_time',
  'material_state',
]
const MES_REFERENCE_LABELS = {
  tracking_card_no: '随行卡号',
  alloy_grade: '合金',
  input_spec: '来料规格',
  output_spec: '成品规格',
  input_weight: '投入重量',
  output_weight: '产出重量',
  on_machine_time: '上机时间',
  off_machine_time: '下机时间',
  material_state: '料态',
}
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
const showMachineEnergyDetails = computed(() =>
  auth.role === 'energy_stat'
  && mode.value === 'per_shift'
  && Array.isArray(form.machine_energy_records)
  && form.machine_energy_records.length > 0
)
const machineEnergyTotalKwh = computed(() => formatMachineEnergyTotal('energy_kwh'))
const machineEnergyTotalGas = computed(() => formatMachineEnergyTotal('gas_m3'))
const historyTitle = computed(() => {
  if (mode.value === 'per_coil') return `本班已录 (${history.value.length}卷)`
  if (mode.value === 'owner_daily') return `${businessDate.value || '本日'} 已录`
  return `本班已录 (${history.value.length})`
})
const mesReferenceRows = computed(() => mesReferenceFields.value.map((item) => ({
  ...item,
  manual: formatReferenceValue(form[item.key]) || '未填',
})))

function formatReferenceValue(value) {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function buildMesReferenceFields(fields = {}) {
  return MES_ASSISTED_SCAN_FIELDS
    .map((key) => {
      const rawValue = key === 'input_spec' ? (fields.input_spec || fields.spec_display) : fields[key]
      const reference = formatReferenceValue(rawValue)
      if (!reference) return null
      return {
        key,
        label: MES_REFERENCE_LABELS[key] || key,
        reference,
      }
    })
    .filter(Boolean)
}

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
  return field.type === 'textarea' || field.type === 'spec' || field.type === 'machine_stop_list'
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
  // If field has spec_suffix, only include p0 and p1 in the submitted form value.
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

function applyScanLookupResult(result) {
  const fields = result?.header_fields || {}
  mesReferenceFields.value = buildMesReferenceFields(fields)
  for (const key of MES_ASSISTED_SCAN_FIELDS) {
    const value = key === 'input_spec' ? (fields.input_spec || fields.spec_display) : fields[key]
    if (value !== undefined && value !== null && key in form) {
      form[key] = value
    }
  }
  for (const g of groups.value) {
    for (const f of g.fields) {
      if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
    }
  }
  lockedFieldsSnapshot.value = {}
  lockedFieldsToken.value = ''
}

function newMachineStopRecord() {
  return {
    workshop_name: workshopName.value,
    machine_name: '',
    machine_code: '',
    shift_name: '',
    downtime_minutes: null,
    downtime_reason: '',
  }
}

function initialFieldValue(field) {
  if (field.type === 'number') return null
  if (field.type === 'machine_stop_list') return [newMachineStopRecord()]
  return ''
}

function machineStopRows(fieldName) {
  return Array.isArray(form[fieldName]) ? form[fieldName] : []
}

function addMachineStopRecord(fieldName) {
  if (!Array.isArray(form[fieldName])) form[fieldName] = []
  form[fieldName].push(newMachineStopRecord())
}

function removeMachineStopRecord(fieldName, index) {
  if (!Array.isArray(form[fieldName])) return
  form[fieldName].splice(index, 1)
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
      if (field.type === 'number') {
        values[field.name] = normalizeNumberValue(value)
      } else if (field.type === 'machine_stop_list') {
        values[field.name] = Array.isArray(value)
          ? value.map((record) => ({ ...record }))
          : []
      } else {
        values[field.name] = value
      }
    }
  }
  return values
}

function currentMachineEnergyRows() {
  return Array.isArray(form.machine_energy_records) ? form.machine_energy_records : []
}

function normalizeMachineEnergyRecords() {
  return currentMachineEnergyRows()
    .map((record) => ({
      machine_id: record.machine_id ?? null,
      machine_code: record.machine_code || '',
      machine_name: record.machine_name || '',
      energy_kwh: normalizeNumberValue(record.energy_kwh),
      gas_m3: normalizeNumberValue(record.gas_m3),
    }))
    .filter((record) => record.energy_kwh !== null || record.gas_m3 !== null)
}

function formatMachineEnergyTotal(fieldName) {
  const values = currentMachineEnergyRows()
    .map((record) => normalizeNumberValue(record[fieldName]))
    .filter((value) => value !== null)
  if (!values.length) return '-'
  const total = values.reduce((sum, value) => sum + value, 0)
  return total.toFixed(2)
}

function syncMachineEnergyRows(savedRecords = []) {
  if (auth.role !== 'energy_stat' || mode.value !== 'per_shift') return
  const records = Array.isArray(savedRecords) ? savedRecords : []
  const savedById = new Map()
  const savedByCode = new Map()
  for (const record of records) {
    if (record?.machine_id !== null && record?.machine_id !== undefined) {
      savedById.set(String(record.machine_id), record)
    }
    if (record?.machine_code) {
      savedByCode.set(String(record.machine_code), record)
    }
  }
  if (workshopMachines.value.length) {
    form.machine_energy_records = workshopMachines.value.map((machine) => {
      const saved = savedById.get(String(machine.machine_id)) || savedByCode.get(String(machine.machine_code)) || {}
      return {
        machine_id: machine.machine_id,
        machine_code: machine.machine_code,
        machine_name: machine.machine_name,
        energy_kwh: saved.energy_kwh ?? null,
        gas_m3: saved.gas_m3 ?? null,
      }
    })
    return
  }
  form.machine_energy_records = records.map((record) => ({ ...record }))
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
    trim_weight: values.trim_weight,
    tray_weight: values.tray_weight,
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
  const machineEnergyRecords = normalizeMachineEnergyRecords()
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
    machine_energy_records: machineEnergyRecords,
    has_exception: Boolean(values.has_exception),
    exception_type: values.exception_type || null,
    note: values.operator_notes || values.energy_note || values.note || null,
  }
}

function buildOwnerDailyPayload(sc) {
  return {
    business_date: ownerDailySelectedDate.value || sc.business_date || inferOwnerDailyBusinessDate(),
    data: normalizedFormValues(),
  }
}

function resetOwnerDailyForm() {
  for (const group of groups.value) {
    for (const field of group.fields) {
      form[field.name] = initialFieldValue(field)
      if (field.type === 'spec') initSpecParts(field.name, '', field.spec_suffix)
    }
  }
  history.value = []
}

async function loadOwnerDailyEntryForDate() {
  const targetDate = ownerDailySelectedDate.value || shiftContext.value?.business_date
  if (!targetDate) return
  ownerDailyLoading.value = true
  resetOwnerDailyForm()
  try {
    const existing = await fetchOwnerDailyEntry(targetDate)
    if (existing?.data) {
      for (const [key, value] of Object.entries(existing.data)) {
        if (key in form && value != null) form[key] = value
      }
      history.value = [existing]
    }
  } catch (e) {
    ElMessage.error(requestErrorMessage(e, '历史数据加载失败'))
  } finally {
    ownerDailyLoading.value = false
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
  if (mode.value === 'owner_daily') {
    const ownerParts = groups.value
      .flatMap(group => group.fields)
      .map(field => summarizeOwnerField(field, d[field.name]))
      .filter(Boolean)
    if (ownerParts.length) return ownerParts.slice(0, 2).join(' · ')
  }
  const parts = []
  if (d.alloy_grade) parts.push(d.alloy_grade)
  if (d.input_weight) parts.push(d.input_weight + '→')
  if (d.output_weight) parts.push(d.output_weight)
  if (d.energy_kwh) parts.push(d.energy_kwh + 'kWh')
  if (d.downtime_minutes) parts.push(d.downtime_minutes + 'min')
  return parts.join(' ') || JSON.stringify(d).slice(0, 40)
}

function summarizeOwnerField(field, value) {
  if (field.type !== 'machine_stop_list') {
    if (value === null || value === undefined || value === '') return ''
    return `${field.label} ${value}${field.unit || ''}`
  }
  const records = Array.isArray(value)
    ? value.filter((record) => record?.machine_name || record?.downtime_minutes || record?.downtime_reason)
    : []
  if (!records.length) return ''
  const details = records.slice(0, 2).map((record) => {
    const machine = record.machine_name || '未标记机台'
    const minutes = record.downtime_minutes ? `${record.downtime_minutes}分钟` : '时长待补'
    const reason = record.downtime_reason ? `（${record.downtime_reason}）` : ''
    return `${machine}停机${minutes}${reason}`
  })
  if (records.length > 2) details.push(`另${records.length - 2}条`)
  return details.join('、')
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
    if (fields.error) {
      error.value = fields.error
      return
    }
    groups.value = fields.groups || []
    readonlyFields.value = fields.readonly_fields || []
    entryRoleLabel.value = fields.role_label || ''
    mode.value = fields.mode || 'per_shift'
    submitTarget.value = fields.submit_target || (fields.mode === 'per_coil' ? 'coil_entry' : 'shift_report')
    identityField.value = fields.identity_field || null
    const requestedTaskBusinessDateRaw = route.query.business_date ?? route.query.businessDate
    const hasRequestedTaskBusinessDate = Array.isArray(requestedTaskBusinessDateRaw)
      ? requestedTaskBusinessDateRaw.some((value) => String(value || '').trim())
      : Boolean(String(requestedTaskBusinessDateRaw || '').trim())
    const requestedTaskBusinessDate = resolveRecentRequestedBusinessDate(
      requestedTaskBusinessDateRaw,
      shift.business_date,
    )
    if (hasRequestedTaskBusinessDate && !requestedTaskBusinessDate) {
      error.value = '补录任务日期无效或已超出可补录范围，请返回异常中心重新发起。'
      return
    }
    const effectiveShift = requestedTaskBusinessDate && mode.value !== 'owner_daily'
      ? { ...shift, business_date: requestedTaskBusinessDate, report_id: null }
      : shift
    shiftContext.value = effectiveShift
    if (!groups.value.length) {
      error.value = fields.error || '当前二维码没有可填报字段，请联系管理员检查岗位模板。'
      return
    }
    if (!effectiveShift.shift_id && mode.value !== 'owner_daily') {
      error.value = '未找到当前班次，请联系管理员配置班次。'
      return
    }

    for (const g of groups.value) {
      for (const f of g.fields) {
        if (!(f.name in form)) form[f.name] = initialFieldValue(f)
        if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
      }
    }

    const allFields = groups.value.flatMap(g => g.fields)
    requestedEntryFields.value = resolveRequestedEntryFields(
      route.query.entry_fields || route.query.entry_field || route.query.entryField || route.query.field,
      allFields,
    )
    loadDynamicOptions(allFields)

    let savedMachineEnergyRecords = []
    if ((effectiveShift.report_id || requestedTaskBusinessDate) && mode.value === 'per_shift') {
      try {
        const report = await fetchMobileReport(effectiveShift.business_date, effectiveShift.shift_id)
        if (report?.data) {
          for (const [k, v] of Object.entries(report.data)) {
            if (k in form && v != null) form[k] = v
          }
        }
        const energyFieldPairs = [
          ['electricity_daily', report?.electricity_daily],
          ['energy_kwh', report?.electricity_daily],
          ['gas_daily', report?.gas_daily],
          ['gas_m3', report?.gas_daily],
        ]
        for (const [key, value] of energyFieldPairs) {
          if (key in form && value != null) form[key] = value
        }
        savedMachineEnergyRecords = report?.machine_energy_records || []
      } catch { /* first time, no report yet */ }
    }
    syncMachineEnergyRows(savedMachineEnergyRecords)

    if (mode.value === 'owner_daily') {
      const latestOwnerDailyDate = shift.business_date || inferOwnerDailyBusinessDate()
      ownerDailySelectedDate.value = resolveOwnerDailyRequestedBusinessDate(
        route.query.business_date || route.query.businessDate,
        latestOwnerDailyDate
      ) || latestOwnerDailyDate
      await loadOwnerDailyEntryForDate()
    }

    if (mode.value === 'per_coil') {
      try {
        const coils = await fetchCoilList(effectiveShift.business_date, effectiveShift.shift_id)
        history.value = Array.isArray(coils) ? coils : []
        coilSeq.value = history.value.length + 1
      } catch { /* no coils yet */ }
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
    await nextTick()
    focusRequestedEntryField()
  }
}

function focusRequestedEntryField() {
  const firstRequestedField = requestedEntryFields.value[0]
  if (!firstRequestedField || typeof document === 'undefined') return
  const target = document.querySelector(`[data-testid="field-${firstRequestedField}"]`)
  if (!target) return
  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
  target.querySelector('input, textarea, select, button')?.focus({ preventScroll: true })
}

async function handleSubmit() {
  if (submitting.value || ownerDailyLoading.value) return
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
      mesReferenceFields.value = []
      resetQuality()
    } else if (submitTarget.value === 'owner_daily') {
      const saved = await saveOwnerDailyEntry(buildOwnerDailyPayload(sc), { skipErrorToast: true })
      if (saved?.business_date) ownerDailySelectedDate.value = saved.business_date
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
  --ue-surface: rgba(6, 24, 42, 0.9);
  --ue-surface-strong: rgba(8, 34, 58, 0.96);
  --ue-border: rgba(0, 197, 255, 0.22);
  --ue-border-soft: rgba(0, 197, 255, 0.12);
  --ue-glow: rgba(0, 197, 255, 0.18);
  position: relative;
  isolation: isolate;
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 920px;
  margin: 0 auto;
  background:
    radial-gradient(circle at 16% 0%, rgba(0, 197, 255, 0.16), transparent 34%),
    radial-gradient(circle at 96% 18%, rgba(34, 92, 255, 0.14), transparent 32%),
    linear-gradient(180deg, rgba(3, 19, 33, 0.96), rgba(2, 10, 20, 0.98));
  color: var(--xt-text);
  overflow-x: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
  padding-bottom: calc(var(--xt-tabbar-height, 64px) + 128px + env(safe-area-inset-bottom, 0px));
}

.unified-entry::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(0, 197, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 197, 255, 0.035) 1px, transparent 1px);
  background-size: 28px 28px;
  -webkit-mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.82), transparent 76%);
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.82), transparent 76%);
  opacity: 0.74;
  z-index: 0;
}

.unified-entry > * {
  position: relative;
  z-index: 1;
}

.ue-identity {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  min-height: 72px;
  padding: 16px 18px;
  background:
    radial-gradient(circle at 22% 0%, color-mix(in srgb, var(--role-color), transparent 68%), transparent 46%),
    linear-gradient(135deg, rgba(0, 197, 255, 0.18), rgba(4, 18, 34, 0.96)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.09), transparent);
  border-bottom: 1px solid var(--ue-border);
  border-left: 3px solid var(--role-color);
  color: var(--xt-text-inverse);
  box-shadow: 0 20px 44px rgba(0, 0, 0, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(14px);
}

.ue-identity::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--role-color), transparent);
  opacity: 0.72;
}

.ue-identity__main {
  position: relative;
  z-index: 1;
}

.ue-identity__main strong {
  display: block;
  font-size: clamp(22px, 6vw, 30px);
  font-weight: 850;
  line-height: 1.18;
  letter-spacing: -0.04em;
  color: var(--xt-text);
  text-shadow: 0 0 22px var(--ue-glow);
}

.ue-identity__main span {
  font-size: 13px;
  color: var(--xt-text-secondary);
  opacity: 1;
}

.ue-loading, .ue-error {
  margin: 16px;
  padding: 32px 16px;
  border: 1px solid var(--ue-border-soft);
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(145deg, var(--ue-surface), rgba(4, 13, 26, 0.82)),
    radial-gradient(circle at 10% 0%, rgba(0, 197, 255, 0.1), transparent 42%);
  text-align: center;
  color: var(--xt-text-secondary);
  font-size: 15px;
}

.ue-error { color: var(--xt-danger); }

.ue-coil-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 14px 16px 0;
  padding: 14px 16px;
  border: 1px solid var(--ue-border-soft);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(6, 31, 54, 0.82), rgba(3, 14, 27, 0.88)),
    radial-gradient(circle at 12% 0%, rgba(0, 197, 255, 0.12), transparent 50%);
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
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
  padding: 16px;
  border: 1px solid color-mix(in srgb, var(--role-color), transparent 68%);
  border-radius: 18px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--role-color), transparent 84%), rgba(5, 14, 28, 0.88)),
    radial-gradient(circle at 12% 0%, rgba(0, 197, 255, 0.12), transparent 48%);
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
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

.ue-owner-date-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ue-owner-date-control label {
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.ue-owner-date-control select {
  min-width: 148px;
  min-height: 40px;
  padding: 0 34px 0 12px;
  border: 1px solid color-mix(in srgb, var(--role-color), transparent 56%);
  border-radius: 8px;
  background: rgba(4, 18, 32, 0.88);
  color: var(--xt-text);
  font: inherit;
}

.ue-scan-row {
  padding: 12px 16px 2px;
}

.ue-scan-btn {
  position: relative;
  overflow: hidden;
  width: 100%;
  min-height: 44px;
  border: 1px solid rgba(0, 197, 255, 0.42);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(0, 197, 255, 0.14), rgba(4, 31, 55, 0.88)),
    radial-gradient(circle at 16% 0%, rgba(255, 255, 255, 0.1), transparent 44%);
  color: var(--xt-primary);
  font-size: 15px;
  font-weight: 800;
  touch-action: manipulation;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 14px 30px rgba(0, 0, 0, 0.24);
  transition: transform 0.12s, border-color 0.16s, box-shadow 0.16s;
}

.ue-scan-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 20%, rgba(255, 255, 255, 0.22), transparent 62%);
  transform: translateX(-120%);
  opacity: 0.16;
}

.ue-scan-btn:active {
  transform: scale(0.98);
}

.ue-mes-reference {
  margin: 12px 16px 0;
  padding: 14px;
  border: 1px solid rgba(0, 197, 255, 0.24);
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(0, 197, 255, 0.1), rgba(3, 15, 28, 0.9)),
    radial-gradient(circle at 10% 0%, rgba(0, 197, 255, 0.12), transparent 44%);
}

.ue-mes-reference header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.ue-mes-reference header strong {
  color: var(--xt-text);
  font-size: 15px;
  font-weight: 900;
}

.ue-mes-reference header span {
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 800;
}

.ue-mes-reference__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.ue-mes-reference__grid article {
  display: grid;
  gap: 4px;
  min-width: 0;
  border: 1px solid rgba(133, 223, 255, 0.14);
  border-radius: 12px;
  padding: 10px;
  background: rgba(2, 13, 25, 0.66);
}

.ue-mes-reference__grid span,
.ue-mes-reference__grid b,
.ue-mes-reference__grid em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ue-mes-reference__grid span {
  color: var(--xt-text-muted);
  font-size: 12px;
}

.ue-mes-reference__grid b {
  color: var(--xt-text);
  font-size: 13px;
}

.ue-mes-reference__grid em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
}

.ue-group {
  margin: 14px 16px 0;
}

.ue-group__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 850;
  letter-spacing: 0.08em;
  color: var(--xt-text-secondary);
  margin: 0 0 9px;
  text-transform: uppercase;
}

.ue-group__title::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--xt-primary);
  box-shadow: 0 0 16px var(--ue-glow);
}

.ue-fields {
  display: grid;
  grid-template-columns: 1fr;
  background:
    linear-gradient(145deg, var(--ue-surface-strong), rgba(4, 13, 26, 0.84)),
    radial-gradient(circle at 12% 0%, rgba(0, 197, 255, 0.1), transparent 44%);
  border: 1px solid var(--ue-border-soft);
  border-radius: 20px;
  box-shadow: 0 20px 44px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  padding: 6px 16px;
}

.ue-field {
  padding: 13px 0;
  border-bottom: 1px solid rgba(0, 197, 255, 0.11);
  min-width: 0;
}

.ue-field:last-child { border-bottom: none; }

.ue-field--requested {
  margin-inline: -10px;
  padding-inline: 10px;
  border-radius: 6px;
  background: rgba(0, 197, 255, 0.08);
  box-shadow: inset 3px 0 0 var(--xt-primary);
}

.ue-field__label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 14px;
  font-weight: 760;
  color: var(--xt-text);
  margin-bottom: 8px;
}

.mobile-required {
  color: var(--xt-danger);
}

.ue-field__unit {
  padding: 1px 7px;
  border: 1px solid rgba(0, 197, 255, 0.18);
  border-radius: 999px;
  background: rgba(0, 197, 255, 0.08);
  font-size: 11px;
  font-weight: 700;
  color: var(--xt-text-secondary);
}

.ue-input {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 9px 13px;
  border: 1px solid rgba(0, 197, 255, 0.18);
  border-radius: 14px;
  font-size: 16px;
  font-family: inherit;
  background:
    linear-gradient(180deg, rgba(4, 17, 32, 0.88), rgba(2, 9, 18, 0.78));
  color: var(--xt-text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
  box-sizing: border-box;
  -webkit-appearance: none;
}

.ue-input:focus {
  border-color: var(--xt-primary);
  background: linear-gradient(180deg, rgba(5, 26, 45, 0.96), rgba(3, 13, 25, 0.9));
  box-shadow: var(--app-focus-ring), inset 0 -1px 0 rgba(0, 197, 255, 0.55), 0 0 24px rgba(0, 197, 255, 0.11);
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
  background: linear-gradient(145deg, rgba(4, 20, 36, 0.86), rgba(2, 10, 20, 0.78));
  border: 1px solid var(--ue-border-soft);
  border-radius: 14px;
  padding: 12px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
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

.ue-machine-energy-list {
  display: grid;
  gap: 10px;
  background:
    linear-gradient(145deg, rgba(4, 20, 36, 0.9), rgba(2, 10, 20, 0.82)),
    radial-gradient(circle at 8% 0%, rgba(24, 220, 180, 0.12), transparent 44%);
  border: 1px solid rgba(24, 220, 180, 0.2);
  border-radius: 20px;
  padding: 12px;
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.ue-machine-energy-row {
  display: grid;
  grid-template-columns: minmax(80px, 0.7fr) minmax(0, 1.3fr);
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid rgba(0, 197, 255, 0.13);
  border-radius: 16px;
  background: rgba(4, 16, 30, 0.72);
}

.ue-machine-energy-name {
  min-width: 0;
  font-size: 14px;
  font-weight: 850;
  color: var(--xt-text);
}

.ue-machine-energy-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.ue-machine-energy-field {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 760;
}

.ue-machine-energy-total {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid rgba(24, 220, 180, 0.2);
  border-radius: 14px;
  background: rgba(24, 220, 180, 0.08);
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-weight: 850;
}

.ue-actions {
  position: sticky;
  bottom: calc(var(--xt-tabbar-height, 64px) + env(safe-area-inset-bottom, 0px) + 8px);
  z-index: 9;
  margin: 16px;
  padding: 10px;
  border: 1px solid var(--ue-border);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(6, 24, 42, 0.94), rgba(3, 10, 20, 0.98)),
    radial-gradient(circle at 50% 0%, rgba(0, 197, 255, 0.14), transparent 54%);
  box-shadow: 0 -16px 38px rgba(0, 0, 0, 0.34), 0 0 34px rgba(0, 197, 255, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(14px);
}

.ue-submit {
  position: relative;
  overflow: hidden;
  display: block;
  width: 100%;
  min-height: 52px;
  border: none;
  border-radius: 15px;
  background:
    linear-gradient(135deg, #00c5ff, #66f2ff 54%, #d8fbff);
  color: #001826;
  font-size: 16px;
  font-weight: 900;
  letter-spacing: 0.05em;
  cursor: pointer;
  touch-action: manipulation;
  box-shadow: 0 0 30px rgba(0, 197, 255, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.5);
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
  opacity: 0.18;
}

.ue-split-btn {
  display: block;
  width: 100%;
  min-height: 44px;
  margin-top: 8px;
  border: 1.5px solid rgba(0, 197, 255, 0.45);
  border-radius: 14px;
  background: rgba(0, 197, 255, 0.07);
  color: var(--xt-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  touch-action: manipulation;
  transition: background 0.15s;
}

.ue-split-btn:active { background: var(--xt-primary-soft); }

.unified-entry :deep(.el-select__wrapper) {
  min-height: 48px;
  border: 1px solid rgba(0, 197, 255, 0.18);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(4, 17, 32, 0.88), rgba(2, 9, 18, 0.78));
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
  background: rgba(0, 197, 255, 0.08);
  border-color: transparent;
  color: var(--xt-text-secondary);
  font-weight: 700;
  text-align: center;
  pointer-events: none;
}

.ue-machine-stops {
  display: grid;
  gap: 10px;
}

.ue-machine-stop {
  padding: 12px;
  border: 1px solid rgba(0, 197, 255, 0.18);
  border-radius: 8px;
  background: rgba(2, 12, 23, 0.64);
}

.ue-machine-stop__heading {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.ue-machine-stop__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
}

.ue-icon-button {
  width: 36px;
  height: 36px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 36px;
  padding: 0;
  border: 1px solid rgba(255, 104, 104, 0.28);
  border-radius: 6px;
  background: rgba(255, 104, 104, 0.08);
  color: var(--xt-danger);
  cursor: pointer;
}

.ue-icon-button svg,
.ue-add-record svg {
  width: 18px;
  height: 18px;
}

.ue-add-record {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid rgba(0, 197, 255, 0.28);
  border-radius: 6px;
  background: rgba(0, 197, 255, 0.08);
  color: var(--xt-primary);
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.ue-history {
  background:
    linear-gradient(145deg, var(--ue-surface), rgba(4, 13, 26, 0.82)),
    radial-gradient(circle at 8% 0%, rgba(0, 197, 255, 0.08), transparent 42%);
  border: 1px solid var(--ue-border-soft);
  border-radius: 20px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
  overflow: hidden;
}

.ue-history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(0, 197, 255, 0.1);
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

  .ue-machine-stop__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ue-machine-stop__reason {
    grid-column: 1 / -1;
  }

  .ue-actions {
    bottom: 18px;
  }
}

@media (max-width: 480px) {
  .ue-identity {
    padding: 12px 14px;
  }

  .ue-fields {
    padding: 2px 12px;
  }

  .ue-field {
    padding: 10px 0;
  }

  .ue-machine-energy-row {
    grid-template-columns: 1fr;
  }

  .ue-mes-reference__grid {
    grid-template-columns: 1fr;
  }

  .ue-actions {
    position: static;
    margin: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ue-submit::after {
    animation: none;
  }

  .ue-scan-btn::after,
  .ue-identity::after {
    animation: none;
  }

  .ue-input,
  .ue-scan-btn,
  .ue-submit,
  .ue-split-btn {
    transition: none;
  }
}
</style>
