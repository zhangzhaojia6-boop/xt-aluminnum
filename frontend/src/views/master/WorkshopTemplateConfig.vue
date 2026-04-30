<template>
  <ReferencePageFrame
    module-number="14"
    title="主数据与模板中心"
    :tags="['字段模板', '车间主数据', '录入口径']"
    data-testid="template-editor-page"
  >
    <template #actions>
      <el-select
        v-model="selectedTemplateKey"
        placeholder="选择车间"
        style="width: 260px"
        filterable
        data-testid="template-workshop-select"
        @change="loadTemplate"
      >
        <el-option
          v-for="workshop in editableWorkshops"
          :key="workshop.code"
          :label="`${workshop.name} (${workshop.code})`"
          :value="workshop.code"
        />
      </el-select>
      <el-button type="primary" :loading="saving" data-testid="template-save" @click="saveTemplate">保存</el-button>
    </template>

    <el-card v-if="currentWorkshop" class="panel">
      <div class="template-meta">
        <div class="template-meta__item">
          <span>车间</span>
          <strong>{{ currentWorkshop.name }}</strong>
        </div>
        <div class="template-meta__item">
          <span>模板键</span>
          <strong>{{ templateForm.template_key || selectedTemplateKey }}</strong>
        </div>
        <div class="template-meta__item">
          <span>基础类型</span>
          <strong>{{ templateForm.workshop_type || currentWorkshop.workshop_type || '-' }}</strong>
        </div>
        <div class="template-meta__item">
          <span>当前来源</span>
          <ReferenceStatusTag
            :status="templateForm.has_override ? 'warning' : 'success'"
            :label="templateForm.has_override ? '车间覆盖' : `继承 ${templateForm.source_template_key || templateForm.workshop_type || '-'}`"
          />
        </div>
      </div>

      <div class="template-config-grid">
        <div class="template-config-grid__item">
          <label>名称</label>
          <el-input v-model="templateForm.display_name" />
        </div>
        <div class="template-config-grid__item">
          <label>节奏</label>
          <el-segmented v-model="templateForm.tempo" :options="tempoOptions" block />
        </div>
        <div class="template-config-grid__item template-config-grid__item--full">
          <label>开关</label>
          <el-checkbox v-model="templateForm.supports_ocr">OCR 识别</el-checkbox>
        </div>
      </div>
    </el-card>

    <template v-if="selectedTemplateKey">
      <el-card v-for="section in sections" :key="section.key" :data-testid="`template-section-${section.key}`" class="panel">
        <template #header>
          <div class="template-section__header">
            <div class="template-section__title">
              <strong>{{ section.label }}</strong>
              <span>{{ templateForm[section.key].length }} 项</span>
            </div>
            <el-button
              class="template-section__add"
              type="primary"
              :data-testid="`template-add-${section.key}`"
              title="新增字段"
              @click="addField(section.key)"
            >
              +
            </el-button>
          </div>
        </template>

        <div v-if="!templateForm[section.key].length" class="template-empty">
          暂无字段
        </div>

        <div v-else class="template-field-list">
          <div v-for="(field, index) in templateForm[section.key]" :key="`${section.key}-${index}-${field.name || 'new'}`" class="template-field-row">
            <div class="template-field-row__main">
              <el-input v-model="field.name" :data-testid="`template-${section.key}-name-${index}`" placeholder="字段键" />
              <el-input v-model="field.label" :data-testid="`template-${section.key}-label-${index}`" placeholder="字段名" />
              <el-select v-model="field.type" :data-testid="`template-${section.key}-type-${index}`" placeholder="类型">
                <el-option label="文本" value="text" />
                <el-option label="数字" value="number" />
                <el-option label="时间" value="time" />
              </el-select>
              <el-input v-model="field.unit" :data-testid="`template-${section.key}-unit-${index}`" placeholder="单位" />
            </div>

            <div class="template-field-row__meta">
              <el-input v-model="field.hint" placeholder="录入提示" />
              <el-input v-model="field.compute" :disabled="section.key !== 'readonly_fields'" placeholder="公式" />
            </div>

            <div class="template-field-row__flags">
              <el-checkbox v-model="field.required" :disabled="section.key === 'readonly_fields'">必填</el-checkbox>
              <el-checkbox v-model="field.enabled">启用</el-checkbox>
            </div>

            <div class="template-field-row__actions">
              <el-button text @click="moveField(section.key, index, -1)" :disabled="index === 0">上移</el-button>
              <el-button text @click="moveField(section.key, index, 1)" :disabled="index === templateForm[section.key].length - 1">下移</el-button>
              <el-button text type="danger" @click="removeField(section.key, index)">删除</el-button>
            </div>
          </div>
        </div>
      </el-card>
    </template>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchWorkshops, fetchWorkshopTemplateConfig, updateWorkshopTemplateConfig } from '../../api/master'

const saving = ref(false)
const selectedTemplateKey = ref('')
const workshops = ref([])
const tempoOptions = [
  { label: '快工序', value: 'fast' },
  { label: '慢工序', value: 'slow' }
]
const sections = [
  { key: 'entry_fields', label: '录入字段' },
  { key: 'shift_fields', label: '班末字段' },
  { key: 'extra_fields', label: '补充字段' },
  { key: 'qc_fields', label: '质检字段' },
  { key: 'readonly_fields', label: '公式字段' }
]

const templateForm = reactive({
  template_key: '',
  workshop_type: '',
  source_template_key: '',
  has_override: false,
  display_name: '',
  tempo: 'fast',
  supports_ocr: false,
  entry_fields: [],
  shift_fields: [],
  extra_fields: [],
  qc_fields: [],
  readonly_fields: []
})

const editableWorkshops = computed(() => workshops.value.filter((item) => item.is_active !== false && item.workshop_type))
const currentWorkshop = computed(() => editableWorkshops.value.find((item) => item.code === selectedTemplateKey.value) || null)

function clonePayload(payload) {
  return JSON.parse(JSON.stringify(payload))
}

function normalizeField(field = {}) {
  return {
    name: field.name || '',
    label: field.label || '',
    type: field.type || 'text',
    unit: field.unit || '',
    hint: field.hint || '',
    compute: field.compute || '',
    required: Boolean(field.required),
    enabled: field.enabled !== false
  }
}

function blankField(sectionKey) {
  return {
    name: '',
    label: '',
    type: sectionKey === 'readonly_fields' ? 'number' : 'text',
    unit: '',
    hint: '',
    compute: '',
    required: false,
    enabled: true
  }
}

function hydrateTemplate(payload) {
  const normalized = clonePayload(payload)
  templateForm.template_key = normalized.template_key || selectedTemplateKey.value
  templateForm.workshop_type = normalized.workshop_type || currentWorkshop.value?.workshop_type || ''
  templateForm.source_template_key = normalized.source_template_key || normalized.workshop_type || ''
  templateForm.has_override = Boolean(normalized.has_override)
  templateForm.display_name = normalized.display_name || ''
  templateForm.tempo = normalized.tempo || 'fast'
  templateForm.supports_ocr = Boolean(normalized.supports_ocr)
  templateForm.entry_fields = (normalized.entry_fields || []).map(normalizeField)
  templateForm.shift_fields = (normalized.shift_fields || []).map(normalizeField)
  templateForm.extra_fields = (normalized.extra_fields || []).map(normalizeField)
  templateForm.qc_fields = (normalized.qc_fields || []).map(normalizeField)
  templateForm.readonly_fields = (normalized.readonly_fields || []).map(normalizeField)
}

async function loadWorkshops() {
  workshops.value = await fetchWorkshops({ limit: 500 })
  if (!selectedTemplateKey.value && editableWorkshops.value.length) {
    selectedTemplateKey.value = editableWorkshops.value[0].code
  }
}

async function loadTemplate() {
  if (!selectedTemplateKey.value) return
  const payload = await fetchWorkshopTemplateConfig(selectedTemplateKey.value)
  hydrateTemplate(payload)
}

function addField(sectionKey) {
  templateForm[sectionKey].push(blankField(sectionKey))
}

function removeField(sectionKey, index) {
  templateForm[sectionKey].splice(index, 1)
}

function moveField(sectionKey, index, delta) {
  const targetIndex = index + delta
  if (targetIndex < 0 || targetIndex >= templateForm[sectionKey].length) return
  const next = [...templateForm[sectionKey]]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  templateForm[sectionKey] = next
}

async function saveTemplate() {
  if (!selectedTemplateKey.value) return
  saving.value = true
  try {
    const payload = {
      display_name: templateForm.display_name,
      tempo: templateForm.tempo,
      supports_ocr: templateForm.supports_ocr,
      entry_fields: templateForm.entry_fields,
      shift_fields: templateForm.shift_fields,
      extra_fields: templateForm.extra_fields,
      qc_fields: templateForm.qc_fields,
      readonly_fields: templateForm.readonly_fields
    }
    const saved = await updateWorkshopTemplateConfig(selectedTemplateKey.value, payload)
    hydrateTemplate(saved)
    ElMessage.success('模板已保存')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadWorkshops()
  await loadTemplate()
})
</script>

<style scoped>
.template-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.template-meta__item,
.template-config-grid__item {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  padding: 14px;
  box-shadow: var(--xt-shadow-xs);
  transition:
    transform var(--xt-motion-fast) var(--xt-ease-out),
    box-shadow var(--xt-motion-fast) var(--xt-ease-out),
    border-color var(--xt-motion-fast) ease;
}

.template-meta__item:hover,
.template-config-grid__item:hover {
  transform: translateY(-1px);
  border-color: var(--xt-info-border);
  box-shadow: var(--xt-shadow-sm);
}

.template-meta__item span,
.template-config-grid__item label {
  color: var(--el-text-color-secondary);
  display: block;
  font-size: 12px;
  margin-bottom: 6px;
  font-weight: 700;
}

.template-meta__item strong {
  color: var(--xt-gray-900);
}

.template-config-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  margin-top: 16px;
}

.template-config-grid__item--full {
  grid-column: 1 / -1;
}

.template-section__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.template-section__title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-section__title span {
  font-size: 12px;
  color: var(--xt-text-secondary);
  background: var(--xt-bg-panel-muted);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-pill);
  min-height: 24px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
}

.template-empty {
  color: var(--xt-text-secondary);
}

.template-section__add {
  width: 40px;
  height: 32px;
  padding: 0;
  border-radius: var(--xt-radius-md);
  font-size: 18px;
  font-weight: 800;
  line-height: 1;
}

.template-field-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.template-field-row {
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  padding: 12px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-xs);
  transition:
    transform var(--xt-motion-fast) var(--xt-ease-out),
    box-shadow var(--xt-motion-fast) var(--xt-ease-out),
    border-color var(--xt-motion-fast) ease;
}

.template-field-row:hover {
  transform: translateY(-1px);
  border-color: var(--xt-info-border);
  box-shadow: var(--xt-shadow-sm);
}

.template-field-row__main,
.template-field-row__meta {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.template-field-row__meta {
  grid-template-columns: 1fr 1fr;
  margin-top: 10px;
}

.template-field-row__flags,
.template-field-row__actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .template-field-row__main,
  .template-field-row__meta {
    grid-template-columns: 1fr;
  }
}
</style>
