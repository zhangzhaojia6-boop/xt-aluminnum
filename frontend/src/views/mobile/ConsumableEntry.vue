<template>
  <div class="mobile-shell mobile-shell--entry" data-testid="consumable-entry">
    <section class="panel">
      <div class="panel-header">
        <h1>辅材填报</h1>
        <p class="panel-subtitle">每日一次，按车间汇总，非必填</p>
      </div>

      <el-alert
        v-if="loadError"
        :title="loadError"
        type="error"
        show-icon
        :closable="false"
        class="panel"
      />

      <el-form label-position="top" class="consumable-form">
        <el-form-item label="车间">
          <el-select
            v-model="selectedWorkshopId"
            placeholder="选择车间"
            :loading="loadingWorkshops"
            @change="onWorkshopChange"
            style="width: 100%"
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
            style="width: 100%"
            @change="loadLog"
          />
        </el-form-item>
      </el-form>

      <div v-if="selectedWorkshop" class="consumable-fields">
        <div class="consumable-fields__hint">
          <span>{{ selectedWorkshop.workshop_name }}</span>
          <span class="consumable-fields__type">{{ workshopTypeLabel }}</span>
        </div>

        <el-form label-position="top" class="consumable-form">
          <el-form-item
            v-for="field in selectedWorkshop.fields"
            :key="field.name"
            :label="field.label"
          >
            <el-input-number
              v-if="isNumericField(field)"
              v-model="formValues[field.name]"
              :min="0"
              :precision="3"
              :step="1"
              :placeholder="field.placeholder || ''"
              style="width: 100%"
              controls-position="right"
            />
            <el-input
              v-else
              v-model="formValues[field.name]"
              :placeholder="field.placeholder || ''"
              clearable
            />
          </el-form-item>

          <el-form-item label="备注">
            <el-input
              v-model="note"
              type="textarea"
              :rows="2"
              placeholder="可选"
            />
          </el-form-item>
        </el-form>

        <div class="consumable-actions">
          <el-button type="primary" :loading="saving" @click="onSave">
            保存
          </el-button>
          <span v-if="lastSavedAt" class="consumable-actions__hint">
            上次保存：{{ lastSavedAt }}
          </span>
        </div>
      </div>

      <el-empty v-else-if="!loadingWorkshops" description="选择车间后开始填报" />
    </section>
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

const workshops = ref([])
const loadingWorkshops = ref(false)
const selectedWorkshopId = ref(null)
const businessDate = ref(formatToday())
const formValues = reactive({})
const note = ref('')
const saving = ref(false)
const lastSavedAt = ref('')
const loadError = ref('')

const selectedWorkshop = computed(() =>
  workshops.value.find((w) => w.workshop_id === selectedWorkshopId.value) || null
)

const workshopTypeLabel = computed(() => selectedWorkshop.value?.workshop_type || '')

function formatToday() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function isNumericField(field) {
  return field.type === 'number' || field.unit
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
.consumable-form {
  margin-top: 12px;
}

.consumable-fields {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(0, 242, 255, 0.1);
}

.consumable-fields__hint {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 14px;
  color: var(--xt-text-secondary);
  margin-bottom: 8px;
}

.consumable-fields__type {
  min-height: 24px;
  padding: 2px 8px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 700;
}

.consumable-actions {
  display: grid;
  grid-template-columns: minmax(120px, 0.8fr) minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.consumable-actions__hint {
  font-size: 12px;
  color: var(--xt-text-muted);
}

.panel-header h1 {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: 22px;
  font-weight: 900;
  letter-spacing: -0.02em;
  text-shadow: 0 0 18px rgba(0, 242, 255, 0.16);
}

.panel-subtitle {
  margin: 4px 0 0;
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.consumable-form :deep(.el-form-item__label) {
  color: var(--xt-text-secondary);
  font-weight: 700;
}

.consumable-form :deep(.el-input-number .el-input__inner) {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 520px) {
  .consumable-actions {
    grid-template-columns: 1fr;
  }
}
</style>
