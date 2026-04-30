<template>
  <div class="unified-entry" data-testid="unified-entry">
    <header class="ue-identity" :style="{ '--role-color': roleColor }">
      <div class="ue-identity__main">
        <strong>{{ roleLabel }}</strong>
        <span>{{ workshopName }} · {{ shiftName }} · {{ businessDate }}</span>
      </div>
    </header>

    <div v-if="loading" class="ue-loading">加载中…</div>
    <div v-else-if="error" class="ue-error">{{ error }}</div>

    <template v-else>
      <div v-if="mode === 'per_coil'" class="ue-coil-header">
        <strong class="ue-coil-seq">第{{ coilSeq }}卷</strong>
        <span class="ue-coil-shift">{{ shiftName }} · 已录{{ history.length }}卷</span>
      </div>

      <section v-for="(group, gi) in groups" :key="gi" class="ue-group">
        <h3 class="ue-group__title">{{ group.label }}</h3>
        <div class="ue-fields">
          <div v-for="field in group.fields" :key="field.name" class="ue-field">
            <label class="ue-field__label">
              {{ field.label }}
              <span v-if="field.unit" class="ue-field__unit">{{ field.unit }}</span>
            </label>
            <select
              v-if="field.type === 'select' && field.options"
              v-model="form[field.name]"
              class="ue-input ue-input--select"
            >
              <option value="">请选择</option>
              <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <div v-else-if="field.type === 'spec'" class="ue-spec-row">
              <input
                v-model="specParts[field.name + '_0']"
                type="text"
                inputmode="decimal"
                class="ue-input ue-spec-input"
                placeholder="厚"
                @input="syncSpec(field)"
              />
              <span class="ue-spec-sep">×</span>
              <input
                v-model="specParts[field.name + '_1']"
                type="text"
                inputmode="decimal"
                class="ue-input ue-spec-input"
                placeholder="宽"
                @input="syncSpec(field)"
              />
              <span class="ue-spec-sep">×</span>
              <input
                v-if="!field.spec_suffix"
                v-model="specParts[field.name + '_2']"
                type="text"
                class="ue-input ue-spec-input"
                placeholder="长/C"
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
              :placeholder="field.hint || field.label"
            />
            <input
              v-else-if="field.type === 'time'"
              v-model="form[field.name]"
              type="time"
              class="ue-input"
            />
            <textarea
              v-else-if="field.type === 'textarea'"
              v-model="form[field.name]"
              class="ue-input ue-input--textarea"
              rows="2"
              :placeholder="field.hint || field.label"
            />
            <input
              v-else
              v-model="form[field.name]"
              type="text"
              class="ue-input"
              :placeholder="field.hint || field.label"
            />
          </div>
        </div>
      </section>

      <section v-if="readonlyFields.length" class="ue-group ue-group--readonly">
        <h3 class="ue-group__title">自动计算</h3>
        <div class="ue-readonly-row">
          <div v-for="rf in readonlyFields" :key="rf.name" class="ue-readonly-item">
            <span class="ue-readonly-item__label">{{ rf.label }}</span>
            <strong class="ue-readonly-item__value">{{ computeReadonly(rf) }}</strong>
          </div>
        </div>
      </section>

      <div class="ue-actions">
        <button class="ue-submit" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中…' : (mode === 'per_coil' ? '录入本卷' : '提交') }}
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
        <h3 class="ue-group__title">{{ mode === 'per_coil' ? `本班已录 (${history.length}卷)` : `本班已录 (${history.length})` }}</h3>
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
import { useAuthStore } from '../../stores/auth.js'
import {
  fetchCurrentShift,
  fetchEntryFields,
  saveMobileReport,
  submitMobileReport,
  fetchMobileReport,
  fetchCoilList,
  createCoilEntry,
} from '../../api/mobile.js'

const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const form = reactive({})
const specParts = reactive({})
const groups = ref([])
const readonlyFields = ref([])
const mode = ref('per_shift')
const history = ref([])
const coilSeq = ref(1)
const lastCoilData = ref(null)

const shiftContext = ref(null)
const workshopName = computed(() => shiftContext.value?.workshop_name || '')
const shiftName = computed(() => shiftContext.value?.shift_name || '')
const businessDate = computed(() => shiftContext.value?.business_date || '')
const roleLabel = computed(() => {
  const labels = {
    machine_operator: '主操',
    energy_stat: '电工',
    maintenance_lead: '机修',
    hydraulic_lead: '液压',
    consumable_stat: '耗材',
    qc: '质检',
    weigher: '称重',
    shift_leader: '班长',
    contracts: '计划科',
    inventory_keeper: '成品库',
    utility_manager: '水电气',
  }
  return labels[auth.role] || auth.displayName
})

const ROLE_COLORS = {
  machine_operator: 'oklch(51% 0.17 255)',
  energy_stat: 'oklch(52% 0.13 158)',
  maintenance_lead: 'oklch(61% 0.12 75)',
  hydraulic_lead: 'oklch(54% 0.095 54)',
  consumable_stat: 'oklch(50% 0.15 252)',
  qc: 'oklch(55% 0.15 28)',
  weigher: 'oklch(43% 0.032 250)',
  contracts: 'oklch(51% 0.17 255)',
  inventory_keeper: 'oklch(54% 0.095 54)',
  utility_manager: 'oklch(52% 0.13 158)',
}
const roleColor = computed(() => ROLE_COLORS[auth.role] || 'oklch(51% 0.17 255)')

function computeReadonly(rf) {
  if (!rf.compute) return '—'
  try {
    const expr = rf.compute.replace(/[a-z_]+/g, (m) => {
      const v = Number(form[m])
      return isNaN(v) ? '0' : String(v)
    })
    const val = Function(`"use strict"; return (${expr})`)()
    if (!isFinite(val)) return '—'
    return rf.unit === '%' ? val.toFixed(1) + '%' : val.toFixed(1) + (rf.unit ? ' ' + rf.unit : '')
  } catch {
    return '—'
  }
}

function syncSpec(field) {
  const p0 = specParts[field.name + '_0'] || ''
  const p1 = specParts[field.name + '_1'] || ''
  const p2 = field.spec_suffix || specParts[field.name + '_2'] || ''
  form[field.name] = [p0, p1, p2].filter(Boolean).join('×')
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
    if (!shift.shift_id) {
      error.value = '未找到当前班次，请联系管理员配置班次。'
      return
    }
    if (fields.error) {
      error.value = fields.error
      return
    }
    groups.value = fields.groups || []
    readonlyFields.value = fields.readonly_fields || []
    mode.value = fields.mode || 'per_shift'

    for (const g of groups.value) {
      for (const f of g.fields) {
        if (!(f.name in form)) form[f.name] = f.type === 'number' ? null : ''
        if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
      }
    }

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

    if (mode.value === 'per_coil') {
      try {
        const coils = await fetchCoilList(shift.business_date, shift.shift_id)
        history.value = coils || []
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
  if (!sc?.shift_id) return

  submitting.value = true
  try {
    if (mode.value === 'per_coil') {
      const coilPayload = {
        business_date: sc.business_date,
        shift_id: sc.shift_id,
        workshop_id: sc.workshop_id,
        machine_id: sc.machine_id,
        seq: coilSeq.value,
        data: { ...form },
      }
      const saved = await createCoilEntry(coilPayload)
      ElMessage.success(`第${coilSeq.value}卷 录入成功`)
      lastCoilData.value = { ...form }
      history.value.unshift(saved?.data ? saved : { seq: coilSeq.value, ...form })
      coilSeq.value++
      for (const key of Object.keys(form)) {
        form[key] = typeof form[key] === 'number' ? null : ''
      }
    } else {
      const payload = {
        business_date: sc.business_date,
        shift_id: sc.shift_id,
        workshop_id: sc.workshop_id,
        team_id: sc.team_id,
        data: { ...form },
      }
      await saveMobileReport(payload)
      await submitMobileReport(payload)
      ElMessage.success('提交成功')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
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
  background: var(--xt-bg-page, #f5f5f7);
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
  background: var(--xt-bg-ink, #1a1a2e);
  border-left: 3px solid var(--role-color);
  color: #fff;
}

.ue-identity__main strong {
  display: block;
  font-size: 20px;
  font-weight: 850;
  line-height: 1.18;
  letter-spacing: -0.012em;
}

.ue-identity__main span {
  font-size: 13px;
  opacity: 0.6;
}

.ue-identity__logout {
  background: none;
  border: 1px solid rgba(255,255,255,0.25);
  color: rgba(255,255,255,0.7);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.ue-loading, .ue-error {
  padding: 48px 16px;
  text-align: center;
  color: var(--xt-text-secondary, #666);
  font-size: 15px;
}

.ue-error { color: var(--xt-text-danger, #d32f2f); }

.ue-coil-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 16px 16px 0;
}

.ue-coil-seq {
  font-family: var(--xt-font-number, 'Bahnschrift', monospace);
  font-size: 28px;
  font-weight: 950;
  letter-spacing: -0.02em;
  color: var(--xt-primary, #3b82f6);
}

.ue-coil-shift {
  font-size: 13px;
  color: var(--xt-text-tertiary, #999);
}

.ue-group {
  margin: 12px 16px 0;
}

.ue-group__title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--xt-text-secondary, #666);
  margin: 0 0 8px;
  text-transform: uppercase;
}

.ue-fields {
  background: var(--xt-bg-panel, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  padding: 4px 16px;
}

.ue-field {
  padding: 12px 0;
  border-bottom: 1px solid var(--xt-border-light, #eee);
}

.ue-field:last-child { border-bottom: none; }

.ue-field__label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--xt-text-primary, #222);
  margin-bottom: 6px;
}
.ue-field__unit {
  font-size: 12px;
  font-weight: 400;
  color: var(--xt-text-tertiary, #999);
}

.ue-input {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid var(--xt-border-default, #ddd);
  border-radius: 8px;
  font-size: 16px;
  font-family: inherit;
  background: var(--xt-bg-page, #f5f5f7);
  color: var(--xt-text-primary, #222);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
  -webkit-appearance: none;
}

.ue-input:focus {
  border-color: var(--xt-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
}

.ue-input--number {
  text-align: right;
  font-family: var(--xt-font-number, 'Bahnschrift', 'DIN Alternate', monospace);
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
  background: var(--xt-bg-panel, #fff);
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.ue-readonly-item__label {
  display: block;
  font-size: 12px;
  color: var(--xt-text-tertiary, #999);
  margin-bottom: 4px;
}

.ue-readonly-item__value {
  font-family: var(--xt-font-number, 'Bahnschrift', monospace);
  font-size: 20px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.012em;
}

.ue-actions {
  padding: 16px;
}

.ue-submit {
  display: block;
  width: 100%;
  min-height: 48px;
  border: none;
  border-radius: 10px;
  background: var(--xt-primary, #3b82f6);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.1s;
}

.ue-submit:active { transform: scale(0.96); }
.ue-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.ue-split-btn {
  display: block;
  width: 100%;
  min-height: 44px;
  margin-top: 8px;
  border: 1.5px solid var(--xt-primary, #3b82f6);
  border-radius: 10px;
  background: transparent;
  color: var(--xt-primary, #3b82f6);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.ue-split-btn:active { background: rgba(59,130,246,0.08); }

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
  color: var(--xt-text-tertiary, #999);
  flex-shrink: 0;
}

.ue-spec-fixed {
  background: var(--xt-bg-panel, #fff);
  border-color: transparent;
  color: var(--xt-text-secondary, #666);
  font-weight: 700;
  text-align: center;
  pointer-events: none;
}

.ue-history {
  background: var(--xt-bg-panel, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  overflow: hidden;
}

.ue-history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--xt-border-light, #eee);
  font-size: 14px;
}

.ue-history-item:last-child { border-bottom: none; }

.ue-history-item__index {
  font-family: var(--xt-font-number, monospace);
  font-weight: 700;
  color: var(--xt-text-tertiary, #999);
  min-width: 28px;
}

.ue-history-item__summary {
  color: var(--xt-text-primary, #222);
}
</style>

