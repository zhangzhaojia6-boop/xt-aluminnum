<template>
  <div class="mobile-shell mobile-shell--entry consumable-hub" data-testid="consumable-entry">
    <section class="consumable-hub__hero panel">
      <div class="consumable-hub__hero-copy">
        <span class="consumable-hub__eyebrow">辅材填报</span>
        <h1>辅材填报</h1>
        <p>每日一录 · 车间辅材</p>
      </div>
      <div class="consumable-hub__hero-readouts">
        <article>
          <span>车间</span>
          <strong>{{ workshops.length }}</strong>
        </article>
        <article>
          <span>字段</span>
          <strong>{{ fieldCount }}</strong>
        </article>
      </div>
    </section>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      :closable="false"
      class="panel consumable-hub__alert"
    />

    <section class="consumable-hub__panel panel">
      <header class="consumable-hub__panel-head">
        <div>
          <span class="consumable-hub__eyebrow">填报控制</span>
          <strong>确认范围</strong>
        </div>
        <span class="consumable-hub__chip">{{ businessDate }}</span>
      </header>

      <el-form label-position="top" class="consumable-form consumable-hub__controls">
        <el-form-item label="车间">
          <el-select
            v-model="selectedWorkshopId"
            placeholder="选择车间"
            :loading="loadingWorkshops"
            @change="onWorkshopChange"
            class="consumable-hub__input"
          >
            <el-option
              v-for="ws in workshops"
              :key="ws.workshop_id"
              :label="`${ws.workshop_code || ''} ${ws.workshop_name}`"
              :value="ws.workshop_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="业务日期">
          <el-date-picker
            v-model="businessDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            class="consumable-hub__input"
            @change="loadLog"
          />
        </el-form-item>
      </el-form>
    </section>

    <section v-if="selectedWorkshop" class="consumable-hub__panel consumable-hub__panel--active panel">
      <header class="consumable-hub__panel-head">
        <div>
          <span class="consumable-hub__eyebrow">车间状态</span>
          <strong>{{ selectedWorkshopTitle }}</strong>
        </div>
        <span class="consumable-hub__status">
          <i aria-hidden="true"></i>{{ saveStatusLabel }}
        </span>
      </header>

      <div class="consumable-hub__signal">
        <span>{{ workshopTypeLabel || '未分类' }}</span>
        <strong>{{ filledCount }} / {{ fieldCount }}</strong>
      </div>

      <div class="consumable-fields consumable-hub__field-grid">
        <article
          v-for="(field, index) in selectedWorkshop.fields"
          :key="field.name"
          class="consumable-hub__field-card"
          :style="{ '--consumable-index': index }"
        >
          <div class="consumable-hub__field-top">
            <div>
              <span>字段 {{ consumableSeq(index) }}</span>
              <strong>{{ field.label }}</strong>
            </div>
            <em v-if="field.unit">{{ field.unit }}</em>
          </div>
          <el-input-number
            v-if="isNumericField(field)"
            v-model="formValues[field.name]"
            :min="0"
            :precision="3"
            :step="1"
            :placeholder="field.placeholder || ''"
            class="consumable-hub__input"
            controls-position="right"
          />
          <el-input
            v-else
            v-model="formValues[field.name]"
            :placeholder="field.placeholder || ''"
            clearable
            class="consumable-hub__input"
          />
        </article>
      </div>

      <div class="consumable-hub__notes">
        <label>备注</label>
        <el-input
          v-model="note"
          type="textarea"
          :rows="2"
          placeholder="可选"
        />
      </div>
    </section>

    <section v-else-if="!loadingWorkshops" class="consumable-hub__empty panel">
      <span class="consumable-hub__empty-node" aria-hidden="true"></span>
      <strong>选择车间后开始填报</strong>
    </section>

    <div class="consumable-hub__dock">
      <el-button
        type="primary"
        size="large"
        class="consumable-hub__save"
        :loading="saving"
        :disabled="!selectedWorkshopId || !businessDate"
        @click="onSave"
      >
        保存
      </el-button>
      <span class="consumable-hub__saved">
        {{ lastSavedAt ? `上次保存：${lastSavedAt}` : '等待保存' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchConsumableWorkshops,
  fetchDailyConsumableLog,
  upsertDailyConsumableLog,
} from '../../api/consumables.js'
import { inferOwnerDailyBusinessDate } from '../../utils/shiftClock.js'

const workshops = ref([])
const loadingWorkshops = ref(false)
const selectedWorkshopId = ref(null)
const businessDate = ref(inferOwnerDailyBusinessDate())
const formValues = reactive({})
const note = ref('')
const saving = ref(false)
const lastSavedAt = ref('')
const loadError = ref('')

const selectedWorkshop = computed(() =>
  workshops.value.find((w) => w.workshop_id === selectedWorkshopId.value) || null
)

const workshopTypeLabel = computed(() => selectedWorkshop.value?.workshop_type || '')
const selectedWorkshopTitle = computed(() => selectedWorkshop.value?.workshop_name || '未选择车间')
const fieldCount = computed(() => selectedWorkshop.value?.fields?.length || 0)
const filledCount = computed(() => {
  return Object.values(formValues).filter((value) => value !== null && value !== undefined && value !== '').length
})
const saveStatusLabel = computed(() => {
  if (saving.value) return '保存中'
  if (lastSavedAt.value) return '已保存'
  return '待保存'
})

function isNumericField(field) {
  return field.type === 'number' || field.unit
}

function consumableSeq(index) {
  return String(index + 1).padStart(2, '0')
}

function resetFormValues(fields) {
  Object.keys(formValues).forEach((k) => delete formValues[k])
  for (const f of fields || []) {
    formValues[f.name] = null
  }
}

async function loadWorkshops() {
  loadingWorkshops.value = true
  loadError.value = ''
  try {
    const data = await fetchConsumableWorkshops()
    workshops.value = data?.items || []
  } catch (err) {
    loadError.value = err?.response?.data?.detail || '车间列表加载失败'
  } finally {
    loadingWorkshops.value = false
  }
}

async function loadLog() {
  if (!selectedWorkshopId.value || !businessDate.value) return
  try {
    const data = await fetchDailyConsumableLog({
      workshop_id: selectedWorkshopId.value,
      business_date: businessDate.value,
    })
    resetFormValues(data.fields)
    Object.assign(formValues, data.payload || {})
    note.value = data.note || ''
    lastSavedAt.value = data.updated_at
      ? new Date(data.updated_at).toLocaleString()
      : ''
  } catch (err) {
    if (err?.response?.status === 404) {
      const ws = selectedWorkshop.value
      resetFormValues(ws?.fields || [])
      note.value = ''
      lastSavedAt.value = ''
    } else {
      ElMessage.error(err?.response?.data?.detail || '加载失败')
    }
  }
}

function onWorkshopChange() {
  const ws = selectedWorkshop.value
  resetFormValues(ws?.fields || [])
  note.value = ''
  lastSavedAt.value = ''
  if (ws) loadLog()
}

async function onSave() {
  if (!selectedWorkshopId.value || !businessDate.value) {
    ElMessage.warning('请先选择车间和日期')
    return
  }
  saving.value = true
  try {
    const payload = {}
    Object.entries(formValues).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') payload[k] = v
    })
    const data = await upsertDailyConsumableLog({
      workshop_id: selectedWorkshopId.value,
      business_date: businessDate.value,
      payload,
      note: note.value || null,
    })
    lastSavedAt.value = data.updated_at
      ? new Date(data.updated_at).toLocaleString()
      : new Date().toLocaleString()
    ElMessage.success('已保存')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadWorkshops)
</script>

<style scoped>
.consumable-hub {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: calc(var(--xt-tabbar-height) + 126px + env(safe-area-inset-bottom, 0px));
}

.consumable-hub::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    radial-gradient(circle at 14% 2%, rgba(0, 242, 255, 0.16), transparent 32%),
    radial-gradient(circle at 100% 24%, rgba(255, 171, 0, 0.1), transparent 24%),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.032) 0 1px, transparent 1px 26px),
    repeating-linear-gradient(0deg, transparent 0 18px, rgba(0, 242, 255, 0.035) 19px 20px);
  opacity: 0.72;
  transform: translateX(-50%);
}

.consumable-hub > * {
  position: relative;
  z-index: 1;
}

.consumable-hub__hero,
.consumable-hub__panel,
.consumable-hub__field-card,
.consumable-hub__dock,
.consumable-hub__empty {
  position: relative;
  overflow: hidden;
}

.consumable-hub__hero {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
}

.consumable-hub__hero::after,
.consumable-hub__panel::after,
.consumable-hub__dock::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 0 38%, rgba(0, 242, 255, 0.12) 49%, transparent 60% 100%);
  opacity: 0;
  transform: translateX(-76%);
}

.consumable-hub__hero::after {
  animation: consumableHubScan 6.5s ease-in-out infinite;
}

.consumable-hub__hero-copy h1,
.consumable-hub__hero-copy p {
  writing-mode: horizontal-tb;
}

.consumable-hub__hero-copy h1 {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: 30px;
  font-weight: 950;
  letter-spacing: -0.04em;
  line-height: 1.05;
  text-shadow: 0 0 22px rgba(0, 242, 255, 0.18);
}

.consumable-hub__hero-copy p {
  margin: 8px 0 0;
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.consumable-hub__hero-readouts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.consumable-hub__hero-readouts article,
.consumable-hub__signal,
.consumable-hub__field-card {
  border: 1px solid rgba(0, 242, 255, 0.16);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent),
    rgba(2, 10, 22, 0.42);
}

.consumable-hub__hero-readouts article {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 14px;
}

.consumable-hub__hero-readouts span,
.consumable-hub__field-top span,
.consumable-hub__saved,
.consumable-hub__chip {
  color: rgba(185, 218, 235, 0.68);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.12em;
}

.consumable-hub__hero-readouts strong {
  color: #e8fdff;
  font-family: var(--xt-font-number);
  font-size: 24px;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.consumable-hub__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: rgba(0, 242, 255, 0.86);
  font-size: 10px;
  font-weight: 950;
  letter-spacing: 0.16em;
}

.consumable-hub__eyebrow::before,
.consumable-hub__status i {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.72);
}

.consumable-hub__panel {
  padding: 12px;
  border-radius: 18px;
}

.consumable-hub__panel--active {
  border-color: rgba(0, 242, 255, 0.24);
}

.consumable-hub__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 14px;
}

.consumable-hub__panel-head strong {
  display: block;
  color: #e8fdff;
  font-size: 18px;
  font-weight: 950;
}

.consumable-hub__chip {
  text-align: right;
}

.consumable-form {
  margin-top: 12px;
}

.consumable-hub__controls {
  margin-top: 0;
}

.consumable-hub__input {
  width: 100%;
}

.consumable-fields {
  margin-top: 16px;
}

.consumable-hub__signal {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 14px;
}

.consumable-hub__signal span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.consumable-hub__signal strong {
  color: #e8fdff;
  font-family: var(--xt-font-number);
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}

.consumable-hub__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #dffbff;
  font-size: 11px;
  font-weight: 950;
  letter-spacing: 0.08em;
}

.consumable-hub__status i {
  animation: consumableHubLed 1.8s ease-in-out infinite;
}

.consumable-hub__field-grid {
  display: grid;
  gap: 12px;
}

.consumable-hub__field-card {
  display: grid;
  gap: 12px;
  padding: 13px;
  border-radius: 16px;
  animation: consumableHubCardIn 420ms ease both;
  animation-delay: calc(var(--consumable-index) * 60ms);
}

.consumable-hub__field-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.consumable-hub__field-top strong {
  display: block;
  margin-top: 4px;
  color: #e8fdff;
  font-size: 17px;
  font-weight: 900;
}

.consumable-hub__field-top em {
  min-width: 38px;
  padding: 4px 8px;
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: #00f2ff;
  font-style: normal;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-align: center;
}

.consumable-hub__notes {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.consumable-hub__notes label {
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 800;
}

.consumable-hub__empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 190px;
  border-radius: 18px;
  text-align: center;
}

.consumable-hub__empty strong {
  color: #e8fdff;
  font-size: 16px;
}

.consumable-hub__empty-node {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  border: 1px solid rgba(0, 242, 255, 0.32);
  background:
    radial-gradient(circle, rgba(0, 242, 255, 0.22) 0 20%, transparent 21%),
    conic-gradient(from 90deg, rgba(0, 242, 255, 0.78), transparent 38%, rgba(255, 171, 0, 0.38), transparent 76%, rgba(0, 242, 255, 0.78));
  box-shadow: 0 0 38px rgba(0, 242, 255, 0.13);
  animation: consumableHubOrbit 5s linear infinite;
}

.consumable-hub__dock {
  position: fixed;
  right: max(14px, calc((100vw - 600px) / 2 + 14px));
  bottom: calc(var(--xt-tabbar-height) + 14px + env(safe-area-inset-bottom, 0px));
  left: max(14px, calc((100vw - 600px) / 2 + 14px));
  z-index: 8;
  display: grid;
  grid-template-columns: minmax(118px, 0.9fr) minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.08), rgba(3, 12, 24, 0.94)),
    rgba(3, 12, 24, 0.88);
  box-shadow: 0 -20px 50px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(16px);
}

.consumable-hub__save {
  position: relative;
  min-height: 44px;
  overflow: hidden;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.16);
}

.consumable-hub__save::after {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  opacity: 0;
  transform: translateX(-100%);
}

.consumable-hub__saved {
  min-width: 0;
  color: rgba(185, 218, 235, 0.72);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.consumable-form :deep(.el-form-item__label) {
  color: var(--xt-text-secondary);
  font-weight: 700;
}

.consumable-hub :deep(.el-select__wrapper),
.consumable-hub :deep(.el-input__wrapper),
.consumable-hub :deep(.el-textarea__inner) {
  border-color: rgba(0, 242, 255, 0.16);
  background: rgba(4, 14, 26, 0.74);
}

.consumable-hub :deep(.el-input__wrapper.is-focus),
.consumable-hub :deep(.el-select__wrapper.is-focused),
.consumable-hub :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px rgba(0, 242, 255, 0.32), 0 0 18px rgba(0, 242, 255, 0.08);
}

.consumable-form :deep(.el-input-number .el-input__inner) {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

@media (hover: hover) {
  .consumable-hub__save:hover::after {
    animation: consumableHubButtonSweep 620ms ease;
  }

  .consumable-hub__field-card:hover {
    border-color: rgba(0, 242, 255, 0.32);
  }
}

.consumable-hub__save:active {
  transform: scale(0.97);
}

@keyframes consumableHubScan {
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

@keyframes consumableHubButtonSweep {
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

@keyframes consumableHubCardIn {
  from {
    opacity: 0;
    transform: translate3d(0, 12px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes consumableHubLed {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes consumableHubOrbit {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 520px) {
  .consumable-hub__dock {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .consumable-hub__hero::after,
  .consumable-hub__field-card,
  .consumable-hub__status i,
  .consumable-hub__empty-node {
    animation: none;
  }
}
</style>
