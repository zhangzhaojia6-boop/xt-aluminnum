<template>
  <div class="mobile-shell mobile-shell--coil" data-testid="coil-entry-workbench">
    <div class="coil-identity" :style="{ '--role-color': 'var(--m-role-operator)' }">
      <div class="coil-identity__main">
        <strong>{{ machineName }}</strong>
        <span>{{ workshopName }}</span>
      </div>
      <div class="coil-identity__shift">
        <span>{{ shiftName }}</span>
        <span>{{ businessDate }}</span>
      </div>
    </div>

    <div class="coil-operator panel">
      <label>我是</label>
      <el-input
        v-model="operatorName"
        placeholder="填你的名字"
        @blur="saveOperatorName"
      />
    </div>

    <section class="coil-mes-pending panel" data-testid="mes-pending-supplements">
      <header class="coil-mes-pending__head">
        <div>
          <span>MES 待补录</span>
          <strong>{{ mesPendingTitle }}</strong>
          <small v-if="mesPendingDateText">{{ mesPendingDateText }}</small>
        </div>
        <el-button size="small" text :loading="mesPendingLoading" @click="loadMesPendingSupplements">
          刷新
        </el-button>
      </header>

      <div v-if="mesPendingLoading && !mesPendingItems.length" class="coil-mes-pending__state">
        正在同步 MES 下机记录…
      </div>
      <div v-else-if="mesPendingError" class="coil-mes-pending__state coil-mes-pending__state--warn">
        {{ mesPendingError }}
      </div>
      <div v-else-if="!mesPendingItems.length" class="coil-mes-pending__state">
        当前机台暂无 MES 待补录卷材。
      </div>
      <div v-else class="coil-mes-pending__list">
        <article
          v-for="item in mesPendingItems"
          :key="item.mes_process_record_id || item.mes_source_id"
          class="coil-mes-card"
          data-testid="mes-pending-card"
        >
          <div class="coil-mes-card__main">
            <strong>{{ pendingTrackingText(item) }}</strong>
            <span>{{ pendingMetaText(item) }}</span>
          </div>
          <div v-if="pendingBadges(item).length" class="coil-mes-card__badges">
            <span v-for="badge in pendingBadges(item)" :key="badge">{{ badge }}</span>
          </div>
          <div class="coil-mes-card__route">
            <span>{{ pendingProcessText(item) }}</span>
            <strong>{{ pendingMachineText(item) }}</strong>
          </div>
          <div class="coil-mes-card__facts">
            <span>
              <em>上机</em>
              <strong>{{ formatKgAsTon(item.input_weight_kg) }}</strong>
            </span>
            <span>
              <em>下机</em>
              <strong>{{ formatKgAsTon(item.output_weight_kg) }}</strong>
            </span>
            <span>
              <em>规格</em>
              <strong>{{ pendingSpecText(item) }}</strong>
            </span>
            <span>
              <em>类型</em>
              <strong>{{ pendingMaterialText(item) }}</strong>
            </span>
          </div>
          <div class="coil-mes-card__metrics">
            <span>{{ formatEndTime(item.end_time) }}</span>
          </div>
          <button class="coil-mes-card__action" type="button" @click="applyMesPendingItem(item)">
            补录
          </button>
        </article>
      </div>
      <footer class="coil-mes-pending__foot">
        MES 已有字段会自动带入，人工值仍可修改。
      </footer>
    </section>

    <div class="coil-summary">
      <article class="coil-summary__item">
        <span>已录</span>
        <strong>{{ coilList.length }}</strong>
        <span>卷</span>
      </article>
      <article class="coil-summary__item">
        <span>投入</span>
        <strong>{{ totalInput }}</strong>
        <span>kg</span>
      </article>
      <article class="coil-summary__item">
        <span>产出</span>
        <strong>{{ totalOutput }}</strong>
        <span>kg</span>
      </article>
      <article class="coil-summary__item">
        <span>成品率</span>
        <strong>{{ yieldRate }}</strong>
        <span>%</span>
      </article>
    </div>

    <div class="coil-list" v-if="coilList.length">
      <div
        v-for="coil in coilList"
        :key="coil.id || coil.tracking_card_no"
        class="coil-list__item"
      >
        <div class="coil-list__left">
          <strong>{{ coil.tracking_card_no }}</strong>
          <span>{{ coil.alloy_grade || '-' }} · {{ coil.output_spec || '-' }}</span>
        </div>
        <div class="coil-list__right">
          <span>{{ coil.input_weight || 0 }} → {{ coil.output_weight || 0 }} kg</span>
        </div>
      </div>
    </div>
    <div v-else class="coil-empty panel">
      本班次暂无录入记录。
    </div>

    <div class="coil-actions">
      <p class="coil-actions__hint">正常先点上方 MES 待补录卡片；找不到卷材时再走兜底。</p>
      <el-button v-if="canScan" size="large" plain :loading="scanning" class="xt-pressable" @click="handleScanLookup()">
        找不到卷材？扫随行卡兜底
      </el-button>
      <el-button type="primary" size="large" class="xt-pressable" @click="openManualEntryDialog">
        手工补录一卷
      </el-button>
      <el-button size="large" plain class="xt-pressable" @click="showSummaryDialog = true">
        本班汇总
      </el-button>
    </div>

    <el-dialog
      v-model="showSummaryDialog"
      title="本班汇总"
      width="92%"
      class="coil-dialog"
    >
      <div class="coil-summary-detail">
        <article class="coil-summary-detail__row">
          <span>总卷数</span><strong>{{ coilList.length }} 卷</strong>
        </article>
        <article class="coil-summary-detail__row">
          <span>总投入</span><strong>{{ totalInput }} kg</strong>
        </article>
        <article class="coil-summary-detail__row">
          <span>总产出</span><strong>{{ totalOutput }} kg</strong>
        </article>
        <article class="coil-summary-detail__row">
          <span>总废料</span><strong>{{ totalScrap }} kg</strong>
        </article>
        <article class="coil-summary-detail__row">
          <span>成品率</span><strong>{{ yieldRate }}%</strong>
        </article>
      </div>
      <template #footer>
        <el-button @click="showSummaryDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showEntryDialog"
      :title="entryDialogTitle"
      :close-on-click-modal="false"
      width="92%"
      class="coil-dialog"
    >
      <div class="mobile-form-grid">
        <section v-if="isMesPendingMode" class="mobile-field mobile-field-wide coil-entry-focus" data-testid="mes-entry-focus">
          <div>
            <span>MES 已带入</span>
            <strong>{{ activeMesTitle }}</strong>
          </div>
          <p>核对机台和现场补录项即可；合金、规格、重量仍可修改。</p>
        </section>
        <section v-if="mesReferenceRows.length" class="mobile-field mobile-field-wide coil-mes-reference" data-testid="mes-assisted-reference">
          <header>
            <strong>MES 参考值</strong>
            <span>人工填报值可改</span>
          </header>
          <div class="coil-mes-reference__grid">
            <article v-for="row in mesReferenceRows" :key="row.key">
              <span>{{ row.label }}</span>
              <b>MES {{ row.reference }}</b>
              <em>人工填报值 {{ row.manual }}</em>
            </article>
          </div>
        </section>
        <div class="mobile-field mobile-field-wide">
          <label><span class="mobile-required">*</span> 卷号</label>
          <el-input v-model="form.tracking_card_no" :disabled="isLockedField('tracking_card_no')" placeholder="手工输入或扫码" @blur="loadFlowSuggestion" />
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 合金</label>
          <el-select v-model="form.alloy_grade" :disabled="isLockedField('alloy_grade')" filterable allow-create default-first-option placeholder="选择或输入">
            <el-option v-for="g in alloyGrades" :key="g.value ?? g" :label="g.label ?? g" :value="g.value ?? g" />
          </el-select>
        </div>
        <div class="mobile-field">
          <label>来料规格</label>
          <div class="mobile-spec-row">
            <el-input :model-value="inputSpecParts[0]" :disabled="isLockedField('input_spec')" inputmode="decimal" placeholder="厚" @update:model-value="updateInputSpec(0, $event)" />
            <span class="mobile-spec-sep">×</span>
            <el-input :model-value="inputSpecParts[1]" :disabled="isLockedField('input_spec')" inputmode="decimal" placeholder="宽" @update:model-value="updateInputSpec(1, $event)" />
            <span class="mobile-spec-sep">×</span>
            <el-input :model-value="inputSpecParts[2]" :disabled="isLockedField('input_spec')" inputmode="decimal" placeholder="长" @update:model-value="updateInputSpec(2, $event)" />
          </div>
        </div>
        <div class="mobile-field">
          <label>成品规格</label>
          <div class="mobile-spec-row">
            <el-input :model-value="outputSpecParts[0]" :disabled="isLockedField('output_spec')" inputmode="decimal" placeholder="厚" @update:model-value="updateOutputSpec(0, $event)" />
            <span class="mobile-spec-sep">×</span>
            <el-input :model-value="outputSpecParts[1]" :disabled="isLockedField('output_spec')" inputmode="decimal" placeholder="宽" @update:model-value="updateOutputSpec(1, $event)" />
            <span class="mobile-spec-sep">×</span>
            <el-input :model-value="outputSpecParts[2]" :disabled="isLockedField('output_spec')" inputmode="decimal" placeholder="长" @update:model-value="updateOutputSpec(2, $event)" />
          </div>
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 投入重量 kg</label>
          <el-input v-model.number="form.input_weight" :disabled="isLockedField('input_weight')" type="number" inputmode="decimal" />
        </div>
        <div class="mobile-field">
          <label><span class="mobile-required">*</span> 产出重量 kg</label>
          <el-input v-model.number="form.output_weight" :disabled="isLockedField('output_weight')" type="number" inputmode="decimal" />
        </div>
        <div class="mobile-field">
          <label>上机时间</label>
          <el-input v-model="form.on_machine_time" :disabled="isLockedField('on_machine_time')" type="time" />
        </div>
        <div class="mobile-field">
          <label>下机时间</label>
          <el-input v-model="form.off_machine_time" :disabled="isLockedField('off_machine_time')" type="time" />
        </div>
        <div class="mobile-field">
          <label>料态</label>
          <el-input v-model="form.material_state" :disabled="isLockedField('material_state')" />
        </div>
        <section class="mobile-field mobile-field-wide coil-flow">
          <header>
            <strong>流转确认</strong>
            <el-button size="small" text :loading="flowLoading" @click="loadFlowSuggestion">同步</el-button>
          </header>
          <div class="coil-flow__grid">
            <label>
              <span>前车间</span>
              <el-input v-model="form.flow.previous_workshop" :disabled="flowFieldState.previous.locked" />
            </label>
            <label>
              <span>前工序</span>
              <el-input v-model="form.flow.previous_process" :disabled="flowFieldState.previous.locked" />
            </label>
            <label>
              <span>当前车间</span>
              <el-input v-model="form.flow.current_workshop" :disabled="flowFieldState.current.locked" />
            </label>
            <label>
              <span>当前工序</span>
              <el-input v-model="form.flow.current_process" :disabled="flowFieldState.current.locked" />
            </label>
            <label>
              <span>下道车间</span>
              <el-input v-model="form.flow.next_workshop" :disabled="flowFieldState.next.locked" @input="markManualFlow" />
            </label>
            <label>
              <span>下道工序</span>
              <el-input v-model="form.flow.next_process" :disabled="flowFieldState.next.locked" @input="markManualFlow" />
            </label>
          </div>
        </section>
        <section class="mobile-field mobile-field-wide coil-quality" data-testid="coil-quality-module">
          <header>
            <strong>填报问题</strong>
            <label>
              <span>有问题</span>
              <el-switch v-model="quality.has_issue" />
            </label>
          </header>
          <div v-if="quality.has_issue" class="coil-quality__fields">
            <label>
              <span>问题类型</span>
              <el-select v-model="quality.issue_type" placeholder="选择类型">
                <el-option label="外观" value="外观" />
                <el-option label="尺寸" value="尺寸" />
                <el-option label="性能" value="性能" />
                <el-option label="包装" value="包装" />
                <el-option label="其他" value="其他" />
              </el-select>
            </label>
            <label>
              <span>问题说明</span>
              <el-input v-model="quality.issue_note" type="textarea" :rows="2" placeholder="简述现场问题" />
            </label>
          </div>
        </section>
        <div class="mobile-field mobile-field-wide">
          <label>备注</label>
          <el-input v-model="form.operator_notes" type="textarea" :rows="2" placeholder="有异常情况写这里" />
        </div>
      </div>
      <template #footer>
        <el-button @click="showEntryDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" class="xt-pressable" @click="submitCoil">提交这卷</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchCurrentShift, fetchFieldOptions, fetchMesPendingSupplements, fetchMobileBootstrap } from '../../api/mobile.js'
import { useAuthStore } from '../../stores/auth.js'
import { api } from '../../api/index.js'
import { validateCoilEntryForm } from '../../utils/coilEntryValidation.js'
import { buildFlowPayload, resolveFlowFieldState } from '../../utils/coilFlowFields.js'
import { DEFAULT_ALLOY_GRADES, loadCoilEntryStartup } from '../../utils/coilEntryStartup.js'
import { useScanLookup } from '../../composables/useScanLookup.js'
import { warnIfMachineMismatch } from '../../composables/useMachineMismatch.js'
import { formatShiftLabel } from '../../utils/display.js'

const route = useRoute()
const auth = useAuthStore()

const bootstrap = ref({})
const currentShift = ref({})
const coilList = ref([])
const mesPending = ref(null)
const mesPendingLoading = ref(false)
const mesPendingError = ref('')
const showEntryDialog = ref(false)
const showSummaryDialog = ref(false)
const submitting = ref(false)
const flowLoading = ref(false)
const operatorName = ref(localStorage.getItem('xt_operator_name') || '')
const lockedFieldsSnapshot = ref({})
const lockedFieldsToken = ref('')
const mesReferenceFields = ref([])
const activeMesPendingItem = ref(null)
const { canScan, scanning, scan, scanLookup } = useScanLookup()

const machineName = computed(() => currentShift.value?.machine_name || bootstrap.value?.machine_name || '-')
const workshopName = computed(() => currentShift.value?.workshop_name || bootstrap.value?.workshop_name || '-')
const shiftName = computed(() => formatShiftLabel(currentShift.value?.shift_name || currentShift.value?.shift_code, '-'))
const businessDate = computed(() => currentShift.value?.business_date || '-')
const mesPendingItems = computed(() => Array.isArray(mesPending.value?.items) ? mesPending.value.items : [])
const mesPendingSummary = computed(() => mesPending.value?.summary || {})
const mesPendingTitle = computed(() => {
  if (!mesPending.value?.is_machine_bound) return '未绑定机台'
  return `${mesPendingSummary.value.pending_count || 0} 卷待补`
})
const mesPendingDateText = computed(() => {
  if (!mesPending.value?.business_date) return ''
  return `${mesPending.value.business_date} · ${mesPending.value.business_day_start || '09:30'} 切日`
})
const isMesPendingMode = computed(() => Boolean(activeMesPendingItem.value))
const entryDialogTitle = computed(() => isMesPendingMode.value ? 'MES 待补录确认' : '手工补录一卷')
const activeMesTitle = computed(() => activeMesPendingItem.value ? pendingTrackingText(activeMesPendingItem.value) : '')

const totalInput = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.input_weight) || 0), 0))
const totalOutput = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.output_weight) || 0), 0))
const totalScrap = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.scrap_weight) || 0), 0))
const yieldRate = computed(() => {
  if (!totalInput.value) return '-'
  return ((totalOutput.value / totalInput.value) * 100).toFixed(1)
})

const alloyGrades = ref(DEFAULT_ALLOY_GRADES)

const emptyFlow = () => ({
  previous_workshop: '',
  previous_process: '',
  current_workshop: '',
  current_process: '',
  next_workshop: '',
  next_process: '',
  flow_source: 'manual',
  flow_confirmed_at: '',
})
const emptyForm = () => ({
  tracking_card_no: '',
  alloy_grade: '',
  input_spec: '',
  output_spec: '',
  on_machine_time: '',
  off_machine_time: '',
  input_weight: null,
  output_weight: null,
  material_state: '',
  operator_notes: '',
  extra_payload: {},
  flow: emptyFlow(),
})
const form = ref(emptyForm())
const quality = reactive({
  has_issue: false,
  issue_type: '',
  issue_note: '',
})
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
const suggestedScrap = computed(() => {
  const inp = Number(form.value.input_weight) || 0
  const out = Number(form.value.output_weight) || 0
  return inp > 0 && out > 0 ? (inp - out).toFixed(1) : ''
})
const mesReferenceRows = computed(() => mesReferenceFields.value.map((item) => ({
  ...item,
  manual: formatReferenceValue(form.value[item.key]) || '未填',
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
}

function buildQualityPayload() {
  if (!quality.has_issue) return null
  return {
    has_issue: true,
    issue_type: quality.issue_type || '',
    issue_note: quality.issue_note || '',
  }
}

function resetEntryContext() {
  activeMesPendingItem.value = null
  lockedFieldsSnapshot.value = {}
  lockedFieldsToken.value = ''
  mesReferenceFields.value = []
  resetQuality()
}

function openManualEntryDialog() {
  form.value = emptyForm()
  resetEntryContext()
  showEntryDialog.value = true
}

function kgNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatKgAsTon(value) {
  const number = kgNumber(value)
  if (number === null) return '-'
  const tons = number / 1000
  return `${tons.toFixed(2).replace(/\.?0+$/, '')} 吨`
}

function formatEndTime(value) {
  if (!value) return '未记录时间'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 16)
  return parsed.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function pendingTrackingText(item) {
  return item.tracking_card_no || item.batch_no || `MES工序 ${item.mes_process_record_id}`
}

function pendingMetaText(item) {
  return [
    item.output_spec || item.input_spec,
    item.alloy_grade,
    item.material_state,
    item.material_code,
    item.customer_alias,
    item.process_name,
  ].filter(Boolean).join('｜') || 'MES 已入账，等待现场补录'
}

const MATERIAL_CATEGORY_TEXT = {
  cold_roll_pass: '冷轧道次',
  hot_roll_process: '热轧坯料',
  cast_roll_process: '铸轧坯料',
  billet_reference: '坯料参考',
  casting_ingot_reference: '铸锭参考',
  coil_process: 'MES工序',
}

function pendingMaterialText(item) {
  return MATERIAL_CATEGORY_TEXT[item.material_category] || 'MES工序'
}

function pendingPassLabel(item) {
  const sequence = item.process_sequence
  if (typeof sequence === 'string') return sequence
  return sequence?.pass_label || ''
}

function pendingProcessText(item) {
  return [
    item.workshop_name,
    item.process_name,
    pendingPassLabel(item),
  ].filter(Boolean).join('｜') || 'MES工序记录'
}

function pendingMachineText(item) {
  if (item.machine_match_status === 'unmatched') return '机台待确认'
  if (item.machine_match_status === 'matched') return '机台已匹配'
  if (item.risk_flags?.includes('machine_match_needs_confirmation')) return '机台待确认'
  if (item.resolved_machine_name || item.mes_machine_name || item.machine_name) return '机台已匹配'
  return '机台未匹配'
}

function pendingSpecText(item) {
  if (item.input_spec && item.output_spec) return `${item.input_spec} → ${item.output_spec}`
  return item.output_spec || item.input_spec || '-'
}

function pendingBadges(item) {
  const badges = []
  const passLabel = pendingPassLabel(item)
  if (passLabel) badges.push(passLabel)
  if (item.material_category === 'cold_roll_pass') badges.push('冷轧道次')
  if (item.material_category === 'hot_roll_process') badges.push('热轧过程')
  if (item.material_category === 'cast_roll_process') badges.push('铸轧过程')
  if (item.material_category === 'billet_reference') badges.push('坯料参考')
  if (item.risk_flags?.includes('machine_match_needs_confirmation')) badges.push('需确认机台')
  if (item.risk_flags?.includes('mes_batch_unmapped')) badges.push('未匹配随行卡')
  return badges
}

function splitSpec(value) {
  const parts = String(value || '').split(/[×xX*]/).map(p => p.trim())
  return [parts[0] || '', parts[1] || '', parts[2] || '']
}
function joinSpec(parts) {
  const clean = parts.map(p => String(p || '').trim())
  if (!clean.some(Boolean)) return ''
  return clean.filter(Boolean).join('×')
}
const inputSpecParts = computed(() => splitSpec(form.value.input_spec))
const outputSpecParts = computed(() => splitSpec(form.value.output_spec))
const flowFieldState = computed(() => resolveFlowFieldState(form.value.flow))
function updateInputSpec(index, value) {
  const parts = splitSpec(form.value.input_spec)
  parts[index] = value
  form.value.input_spec = joinSpec(parts)
}
function updateOutputSpec(index, value) {
  const parts = splitSpec(form.value.output_spec)
  parts[index] = value
  form.value.output_spec = joinSpec(parts)
}

function saveOperatorName() {
  if (operatorName.value) {
    localStorage.setItem('xt_operator_name', operatorName.value)
  }
}

function markManualFlow() {
  if (!flowFieldState.value.next.locked) {
    form.value.flow.flow_source = 'manual'
  }
}

function applyFlowSuggestion(flow) {
  if (!flow) return
  form.value.flow = {
    previous_workshop: flow.previous_workshop || '',
    previous_process: flow.previous_process || '',
    current_workshop: flow.current_workshop || '',
    current_process: flow.current_process || '',
    next_workshop: flow.next_workshop || '',
    next_process: flow.next_process || '',
    flow_source: flow.flow_source || 'mes_projection',
    flow_confirmed_at: new Date().toISOString(),
  }
}

function isLockedField(name) {
  return Object.prototype.hasOwnProperty.call(lockedFieldsSnapshot.value, name)
}

function applyScanLookupResult(result) {
  const fields = result?.header_fields || {}
  activeMesPendingItem.value = null
  resetQuality()
  mesReferenceFields.value = buildMesReferenceFields(fields)
  for (const key of MES_ASSISTED_SCAN_FIELDS) {
    const value = key === 'input_spec' ? (fields.input_spec || fields.spec_display) : fields[key]
    if (value !== undefined && value !== null && key in form.value) {
      form.value[key] = value
    }
  }
  if (fields.current_workshop || fields.current_process || fields.next_workshop || fields.next_process) {
    form.value.flow = {
      ...form.value.flow,
      current_workshop: fields.current_workshop || form.value.flow.current_workshop,
      current_process: fields.current_process || form.value.flow.current_process,
      next_workshop: fields.next_workshop || form.value.flow.next_workshop,
      next_process: fields.next_process || form.value.flow.next_process,
      flow_source: 'scan_lookup',
      flow_confirmed_at: new Date().toISOString(),
    }
  }
  lockedFieldsSnapshot.value = {}
  lockedFieldsToken.value = ''
  showEntryDialog.value = true
}

function buildMesPendingHeaderFields(item) {
  return {
    tracking_card_no: item.tracking_card_no || item.batch_no || '',
    alloy_grade: item.alloy_grade || '',
    input_spec: item.input_spec || '',
    output_spec: item.output_spec || '',
    input_weight: item.input_weight_kg ?? null,
    output_weight: item.output_weight_kg ?? null,
    off_machine_time: item.end_time ? formatEndTime(item.end_time) : '',
    material_state: item.material_state || '',
  }
}

function applyMesPendingItem(item) {
  const fields = buildMesPendingHeaderFields(item)
  const baseForm = emptyForm()
  activeMesPendingItem.value = item
  resetQuality()
  form.value = {
    ...baseForm,
    ...fields,
    extra_payload: {
      ...(baseForm.extra_payload || {}),
      mes_reference: item.mes_reference || {
        process_record_id: item.mes_process_record_id,
        source_id: item.mes_source_id,
        batch_no: item.batch_no,
        tracking_card_no: item.tracking_card_no,
        material_code: item.material_code,
        mes_machine_name: item.mes_machine_name,
        mes_worker_name: item.mes_worker_name,
        resolved_machine_id: item.resolved_machine_id,
        resolved_machine_name: item.resolved_machine_name,
        machine_binding_source: item.machine_binding_source,
        machine_binding_confidence: item.machine_binding_confidence,
        mes_end_time: item.end_time,
        mes_last_seen_at: item.mes_last_seen_at,
        material_reference: item.material_reference,
        process_sequence: item.process_sequence,
      },
    },
  }
  mesReferenceFields.value = buildMesReferenceFields(fields)
  lockedFieldsSnapshot.value = {}
  lockedFieldsToken.value = ''
  showEntryDialog.value = true
  ElMessage.success('已带入 MES 下机数据')
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

async function loadFlowSuggestion() {
  const trackingCardNo = String(form.value.tracking_card_no || '').trim()
  if (!trackingCardNo || flowLoading.value) return
  flowLoading.value = true
  try {
    const { data: flow } = await api.get('/mobile/coil-flow-suggestion', {
      params: { tracking_card_no: trackingCardNo },
      skipErrorToast: true
    })
    applyFlowSuggestion(flow)
  } catch {
    // Flow suggestion is best-effort; manual flow stays available.
  } finally {
    flowLoading.value = false
  }
}

async function loadData() {
  try {
    const startup = await loadCoilEntryStartup({
      fetchMobileBootstrap,
      fetchCurrentShift,
      fetchFieldOptions,
    })
    bootstrap.value = startup.bootstrap
    currentShift.value = startup.currentShift
    alloyGrades.value = startup.alloyGrades
    await Promise.all([loadCoils(), loadMesPendingSupplements()])
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

async function loadMesPendingSupplements() {
  if (mesPendingLoading.value) return
  mesPendingLoading.value = true
  mesPendingError.value = ''
  try {
    mesPending.value = await fetchMesPendingSupplements({
      limit: 20,
    })
  } catch (e) {
    mesPending.value = null
    mesPendingError.value = e?.response?.data?.detail || 'MES 待补录列表加载失败'
  } finally {
    mesPendingLoading.value = false
  }
}

async function loadCoils() {
  const bd = currentShift.value?.business_date
  const sid = currentShift.value?.shift_id
  if (!bd || !sid) return
  try {
    const { data } = await api.get(`/mobile/coil-list/${bd}/${sid}`)
    coilList.value = data || []
  } catch {
    coilList.value = []
  }
}

async function submitCoil() {
  const validationMessage = validateCoilEntryForm(form.value)
  if (validationMessage) {
    ElMessage.warning(validationMessage)
    return
  }
  submitting.value = true
  try {
    const flowPayload = buildFlowPayload(form.value.flow)
    const qualityPayload = buildQualityPayload()
    const extraPayload = {
      ...(form.value.extra_payload || {}),
      ...(flowPayload.extra_payload || {}),
      ...(qualityPayload ? { quality_issue: qualityPayload } : {}),
    }
    const payload = {
      ...form.value,
      on_machine_time: form.value.on_machine_time,
      off_machine_time: form.value.off_machine_time,
      material_state: form.value.material_state,
      scrap_weight: Number(suggestedScrap.value) || 0,
      operator_name: operatorName.value,
      business_date: currentShift.value?.business_date,
      shift_id: currentShift.value?.shift_id,
      locked_fields_snapshot: lockedFieldsSnapshot.value,
      locked_fields_token: lockedFieldsToken.value,
      extra_payload: Object.keys(extraPayload).length ? extraPayload : null,
    }
    delete payload.flow
    await api.post('/mobile/coil-entry', payload)
    ElMessage.success('提交成功')
    form.value = emptyForm()
    resetEntryContext()
    showEntryDialog.value = false
    await Promise.all([loadCoils(), loadMesPendingSupplements()])
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.mobile-shell--coil {
  display: grid;
  gap: var(--xt-space-3);
}

.coil-identity {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: var(--xt-space-4);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-ink);
  border-left: 3px solid var(--role-color, var(--xt-primary));
  box-shadow: var(--xt-shadow-md);
}

.coil-identity__main {
  display: grid;
  gap: 2px;
}

.coil-identity__main strong {
  color: rgba(255, 255, 255, 0.92);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-xl);
  font-weight: 850;
  letter-spacing: 0;
}

.coil-identity__main span,
.coil-identity__shift span {
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--xt-text-sm);
}

.coil-identity__shift {
  display: grid;
  gap: 2px;
  text-align: right;
}

.coil-identity__shift span:first-child {
  color: rgba(255, 255, 255, 0.82);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.coil-operator {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
}

.coil-operator label {
  font-weight: 850;
  font-size: var(--xt-text-lg);
  white-space: nowrap;
}

.coil-mes-pending {
  display: grid;
  gap: 12px;
  padding: 14px;
  overflow: hidden;
  border: 1px solid rgba(0, 197, 255, 0.18);
  background:
    linear-gradient(135deg, rgba(0, 119, 255, 0.14), rgba(4, 16, 30, 0.92)),
    radial-gradient(circle at 0% 0%, rgba(0, 197, 255, 0.14), transparent 48%);
}

.coil-mes-pending__head,
.coil-mes-pending__foot,
.coil-mes-card {
  position: relative;
  z-index: 1;
}

.coil-mes-pending__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.coil-mes-pending__head div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.coil-mes-pending__head span,
.coil-mes-pending__head small,
.coil-mes-pending__foot {
  color: rgba(171, 213, 235, 0.72);
  font-size: var(--xt-text-xs);
}

.coil-mes-pending__head small {
  color: rgba(133, 223, 255, 0.78);
}

.coil-mes-pending__head strong {
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.coil-mes-pending__state {
  padding: 14px;
  border: 1px dashed rgba(133, 223, 255, 0.2);
  border-radius: var(--xt-radius-lg);
  color: var(--xt-text-secondary);
  background: rgba(2, 13, 25, 0.48);
  text-align: center;
}

.coil-mes-pending__state--warn {
  color: var(--xt-warning);
}

.coil-mes-pending__list {
  display: grid;
  gap: 8px;
}

.coil-mes-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(133, 223, 255, 0.16);
  border-radius: var(--xt-radius-lg);
  background: rgba(2, 13, 25, 0.68);
}

.coil-mes-card__main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.coil-mes-card__main strong,
.coil-mes-card__main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coil-mes-card__main strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.coil-mes-card__main span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  line-height: 1.45;
  overflow-wrap: anywhere;
  white-space: normal;
}

.coil-mes-card__metrics {
  display: flex;
  grid-column: 1 / -1;
  gap: 8px;
  flex-wrap: wrap;
}

.coil-mes-card__route {
  display: flex;
  grid-column: 1 / -1;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  padding: 8px 0;
  border-top: 1px solid rgba(133, 223, 255, 0.1);
  border-bottom: 1px solid rgba(133, 223, 255, 0.1);
}

.coil-mes-card__route span,
.coil-mes-card__route strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coil-mes-card__route span {
  min-width: 0;
  color: rgba(211, 237, 249, 0.9);
  font-size: var(--xt-text-sm);
  font-weight: 850;
}

.coil-mes-card__route strong {
  flex: 0 0 auto;
  padding: 3px 7px;
  border: 1px solid rgba(88, 255, 185, 0.2);
  border-radius: 6px;
  background: rgba(33, 211, 146, 0.1);
  color: rgba(132, 255, 210, 0.94);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.coil-mes-card__facts {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.coil-mes-card__facts span {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid rgba(0, 197, 255, 0.13);
  border-radius: 8px;
  background: rgba(4, 22, 40, 0.72);
}

.coil-mes-card__facts em {
  color: rgba(185, 202, 203, 0.72);
  font-size: var(--xt-text-xs);
  font-style: normal;
  font-weight: 800;
}

.coil-mes-card__facts strong {
  overflow: hidden;
  color: rgba(225, 253, 255, 0.94);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
  font-weight: 950;
  overflow-wrap: anywhere;
  text-overflow: ellipsis;
  white-space: normal;
}

.coil-mes-card__badges {
  display: flex;
  grid-column: 1 / -1;
  gap: 6px;
  flex-wrap: wrap;
}

.coil-mes-card__badges span {
  padding: 3px 8px;
  border: 1px solid rgba(93, 234, 255, 0.18);
  border-radius: 999px;
  color: #8feaff;
  background: rgba(0, 197, 255, 0.1);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.coil-mes-card__metrics span {
  padding: 4px 8px;
  border: 1px solid rgba(0, 197, 255, 0.16);
  border-radius: 999px;
  color: rgba(211, 237, 249, 0.86);
  background: rgba(0, 120, 255, 0.1);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xs);
}

.coil-mes-card__action {
  justify-self: end;
  min-width: 78px;
  min-height: 48px;
  border: 0;
  border-radius: 8px;
  color: #f8fbff;
  background: #0052d9;
  font-weight: 900;
}

.coil-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.coil-summary__item {
  display: grid;
  gap: 2px;
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  box-shadow: var(--xt-shadow-xs);
}

.coil-summary__item span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.coil-summary__item strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.coil-list {
  display: grid;
  gap: 1px;
  background: var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  overflow: hidden;
  box-shadow: var(--xt-shadow-sm);
}

.coil-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
}

.coil-list__left {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.coil-list__left strong {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 700;
  color: var(--xt-text);
}

.coil-list__left span {
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
}

.coil-list__right {
  text-align: right;
  white-space: nowrap;
}

.coil-list__right span {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
  font-variant-numeric: tabular-nums;
  color: var(--xt-text-secondary);
}

.coil-empty {
  padding: var(--xt-space-6);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-lg);
}

.coil-actions {
  position: sticky;
  bottom: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom, 0px) + 8px);
  z-index: 10;
  display: grid;
  gap: 8px;
  box-sizing: border-box;
  min-width: 0;
  width: auto;
  max-width: 100%;
  padding: 10px;
  border: 1px solid rgba(0, 197, 255, 0.18);
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(180deg, rgba(5, 19, 34, 0.94), rgba(2, 10, 20, 0.98)),
    radial-gradient(circle at 50% 0%, rgba(0, 197, 255, 0.12), transparent 58%);
  box-shadow: 0 -14px 34px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(12px);
}

.coil-actions__hint {
  margin: 0;
  color: rgba(171, 213, 235, 0.72);
  font-size: var(--xt-text-xs);
  line-height: 1.45;
  text-align: center;
}

.coil-actions .el-button {
  box-sizing: border-box;
  justify-self: center;
  width: calc(100% - 2px);
  min-height: 52px;
  border-radius: var(--xt-radius-lg);
  font-size: var(--xt-text-lg);
  font-weight: 900;
  box-shadow: var(--xt-shadow-md);
}

.coil-summary-detail {
  display: grid;
  gap: 1px;
  background: var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  overflow: hidden;
}

.coil-summary-detail__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
}

.coil-summary-detail__row span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-lg);
}

.coil-summary-detail__row strong {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.coil-entry-focus,
.coil-quality {
  display: grid;
  gap: 10px;
  border: 1px solid rgba(133, 223, 255, 0.16);
  border-radius: var(--xt-radius-lg);
  padding: 12px;
  background: rgba(2, 13, 25, 0.66);
}

.coil-entry-focus div,
.coil-quality header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.coil-entry-focus span,
.coil-entry-focus p,
.coil-quality header span,
.coil-quality__fields span {
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.coil-entry-focus strong {
  overflow: hidden;
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 16px;
  font-weight: 950;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coil-entry-focus p {
  margin: 0;
  line-height: 1.5;
}

.coil-quality header strong {
  color: var(--xt-text);
  font-size: 15px;
  font-weight: 900;
}

.coil-quality header label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.coil-quality__fields {
  display: grid;
  gap: 10px;
}

.coil-quality__fields label {
  display: grid;
  gap: 6px;
}

.coil-mes-reference {
  display: grid;
  gap: 10px;
  border: 1px solid rgba(0, 197, 255, 0.22);
  border-radius: var(--xt-radius-lg);
  padding: 12px;
  background:
    linear-gradient(135deg, rgba(0, 197, 255, 0.1), rgba(3, 15, 28, 0.9)),
    radial-gradient(circle at 10% 0%, rgba(0, 197, 255, 0.12), transparent 44%);
}

.coil-mes-reference header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: baseline;
}

.coil-mes-reference header strong {
  color: var(--xt-text);
  font-size: 15px;
  font-weight: 900;
}

.coil-mes-reference header span {
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 800;
}

.coil-mes-reference__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.coil-mes-reference__grid article {
  display: grid;
  gap: 4px;
  min-width: 0;
  border: 1px solid rgba(133, 223, 255, 0.14);
  border-radius: 12px;
  padding: 10px;
  background: rgba(2, 13, 25, 0.66);
}

.coil-mes-reference__grid span,
.coil-mes-reference__grid b,
.coil-mes-reference__grid em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coil-mes-reference__grid span {
  color: var(--xt-text-muted);
  font-size: 12px;
}

.coil-mes-reference__grid b {
  color: var(--xt-text);
  font-size: 13px;
}

.coil-mes-reference__grid em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
}

@media (max-width: 400px) {
  .coil-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .coil-mes-card {
    grid-template-columns: minmax(0, 1fr);
  }

  .coil-mes-card__action {
    justify-self: stretch;
  }

  .coil-mes-reference__grid {
    grid-template-columns: 1fr;
  }
}

.mobile-spec-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mobile-spec-row .el-input {
  flex: 1;
  min-width: 0;
}

.mobile-spec-row .el-input :deep(.el-input__inner) {
  text-align: center;
}

.mobile-spec-sep {
  font-size: 16px;
  font-weight: 700;
  color: var(--xt-text-muted);
  flex-shrink: 0;
}
</style>
