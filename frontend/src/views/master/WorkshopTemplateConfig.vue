<template>
  <section class="page-stack template-center" data-testid="template-editor-page" aria-labelledby="template-center-title">
    <header class="template-center__hero">
      <div class="template-center__title-block">
        <span class="template-center__eyebrow">FIELD TEMPLATE MATRIX</span>
        <h1 id="template-center-title">模板中心</h1>
      </div>
      <div class="template-center__hero-actions">
        <el-select
          class="template-center__workshop-select"
          v-model="selectedTemplateKey"
          placeholder="选择车间"
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
        <el-button class="template-center__save" type="primary" :loading="saving" data-testid="template-save" @click="saveTemplate">保存</el-button>
      </div>
    </header>

    <section v-if="currentWorkshop" class="template-center__overview" aria-label="模板状态">
      <article class="template-center__overview-card is-workshop">
        <span>车间</span>
        <strong>{{ currentWorkshop.name }}</strong>
        <small>{{ currentWorkshop.code }}</small>
      </article>
      <article class="template-center__overview-card">
        <span>模板键</span>
        <strong>{{ templateForm.template_key || selectedTemplateKey }}</strong>
        <small>{{ templateForm.workshop_type || currentWorkshop.workshop_type || '-' }}</small>
      </article>
      <article
        v-for="stat in templateStats"
        :key="stat.label"
        class="template-center__overview-card"
        :class="`is-${stat.tone}`"
      >
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
        <small>{{ stat.meta }}</small>
      </article>
    </section>

    <el-card v-if="currentWorkshop" class="panel template-center__config" shadow="never">
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
      <el-card
        v-for="section in sections"
        :key="section.key"
        :data-testid="`template-section-${section.key}`"
        class="panel template-center__section"
        shadow="never"
      >
        <template #header>
          <div class="template-section__header">
            <div class="template-section__title">
              <strong>{{ section.label }}</strong>
              <span>{{ templateForm[section.key].length }} 字段</span>
            </div>
            <el-button
              class="template-section__add"
              type="primary"
              :data-testid="`template-add-${section.key}`"
              title="新增字段"
              @click="addField(section.key)"
            >
              + 新增字段
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

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
const allFields = computed(() => sections.flatMap((section) => templateForm[section.key]))
const enabledFieldCount = computed(() => allFields.value.filter((field) => field.enabled !== false).length)
const requiredFieldCount = computed(() => allFields.value.filter((field) => field.required).length)
const formulaFieldCount = computed(() => templateForm.readonly_fields.filter((field) => field.enabled !== false).length)
const templateStats = computed(() => [
  { label: '字段总数', value: allFields.value.length, meta: '五类字段', tone: 'primary' },
  { label: '启用字段', value: enabledFieldCount.value, meta: '当前模板', tone: 'success' },
  { label: '必填字段', value: requiredFieldCount.value, meta: '录入口径', tone: 'warning' },
  { label: '公式字段', value: formulaFieldCount.value, meta: templateForm.has_override ? '车间覆盖' : `继承 ${templateForm.source_template_key || templateForm.workshop_type || '-'}`, tone: 'info' }
])

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
.template-center {
  position: relative;
  isolation: isolate;
  display: grid;
  gap: 16px;
  overflow-x: clip;
  background: transparent;
  --template-accent: #00f2ff;
  --template-accent-soft: rgba(0, 242, 255, 0.12);
  --template-line: rgba(0, 242, 255, 0.16);
  --template-line-strong: rgba(0, 242, 255, 0.38);
  --template-panel: rgba(7, 29, 51, 0.88);
  --template-panel-deep: rgba(2, 12, 25, 0.94);
  --template-text: rgba(225, 253, 255, 0.94);
  --template-muted: rgba(185, 223, 235, 0.64);
  --template-success: #4ecb8a;
  --template-warning: #ffab00;
}

.template-center::before {
  position: absolute;
  inset: -22px 0 auto;
  z-index: -1;
  height: 280px;
  border-radius: 18px;
  background:
    linear-gradient(rgba(0, 242, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.05) 1px, transparent 1px),
    radial-gradient(circle at 18% 12%, rgba(0, 242, 255, 0.18), transparent 28%),
    radial-gradient(circle at 86% 4%, rgba(0, 118, 255, 0.2), transparent 30%);
  background-size: 32px 32px, 32px 32px, auto, auto;
  content: "";
  pointer-events: none;
}

.template-center__hero {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  overflow: hidden;
  padding: 20px;
  border: 1px solid var(--template-line);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(7, 29, 51, 0.94), rgba(2, 13, 26, 0.96)),
    repeating-linear-gradient(90deg, rgba(0, 242, 255, 0.08) 0 1px, transparent 1px 42px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 18px 42px rgba(0, 18, 42, 0.22);
}

.template-center__hero::after {
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.78), transparent);
  animation: templateScanline 4.8s linear infinite;
  content: "";
}

.template-center__title-block {
  min-width: 0;
}

.template-center__eyebrow {
  display: inline-flex;
  color: rgba(116, 245, 255, 0.78);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 0.12em;
}

.template-center__title-block h1 {
  margin: 6px 0 0;
  color: var(--template-text);
  font-family: var(--xt-font-number);
  font-size: clamp(26px, 3vw, 40px);
  letter-spacing: -0.03em;
  line-height: 1.05;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.16);
}

.template-center__hero-actions {
  min-width: min(100%, 360px);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.template-center__workshop-select {
  width: min(260px, 100%);
  min-width: 0;
  flex: 1 1 260px;
}

.template-center__workshop-select :deep(.el-select__wrapper),
.template-center :deep(.el-input__wrapper),
.template-center :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 8px;
  background: rgba(1, 16, 31, 0.84);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.24),
    inset 0 0 0 1px rgba(0, 242, 255, 0.16);
}

.template-center :deep(.el-input__inner),
.template-center :deep(.el-select__selected-item),
.template-center :deep(.el-select__placeholder) {
  color: var(--template-text);
}

.template-center__save {
  min-height: 38px;
  border-color: transparent;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(116, 245, 255, 0.98), rgba(0, 185, 214, 0.92)),
    var(--template-accent);
  color: #00252b;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.22);
  font-weight: 850;
}

.template-center__overview {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) minmax(180px, 1.3fr) repeat(4, minmax(120px, 1fr));
  gap: 12px;
}

.template-center__overview-card {
  position: relative;
  min-height: 108px;
  display: grid;
  align-content: space-between;
  overflow: hidden;
  padding: 16px;
  border: 1px solid var(--template-line);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.82), rgba(3, 14, 27, 0.9)),
    radial-gradient(circle at 100% 0%, rgba(0, 242, 255, 0.12), transparent 34%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.template-center__overview-card.is-workshop {
  grid-column: auto;
}

.template-center__overview-card::after {
  position: absolute;
  inset: auto 14px 10px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.82), transparent);
  content: "";
}

.template-center__overview-card.is-success::after {
  background: linear-gradient(90deg, rgba(78, 203, 138, 0.9), transparent);
}

.template-center__overview-card.is-warning::after {
  background: linear-gradient(90deg, rgba(255, 171, 0, 0.9), transparent);
}

.template-center__overview-card span,
.template-center__overview-card small,
.template-meta__item span,
.template-config-grid__item label {
  color: var(--template-muted);
  font-size: 11px;
  font-weight: 840;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.template-center__overview-card strong {
  min-width: 0;
  overflow: hidden;
  color: var(--template-text);
  font-family: var(--xt-font-number);
  font-size: clamp(24px, 2.4vw, 34px);
  line-height: 1.05;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-center__overview-card:not(.is-workshop) strong {
  font-size: clamp(22px, 2vw, 30px);
  letter-spacing: -0.04em;
}

.template-center__config,
.template-center__section {
  border: 1px solid var(--template-line);
  border-radius: 14px;
  background:
    linear-gradient(180deg, var(--template-panel), var(--template-panel-deep)),
    rgba(3, 16, 31, 0.92);
  color: var(--template-text);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 22px 52px rgba(0, 18, 42, 0.24);
}

.template-center__config :deep(.el-card__body),
.template-center__section :deep(.el-card__body) {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.template-center__section :deep(.el-card__header) {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 242, 255, 0.12);
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.08), transparent 72%);
}

.template-meta,
.template-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.template-config-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  margin-top: 16px;
}

.template-meta__item,
.template-config-grid__item {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.62), rgba(2, 12, 25, 0.7)),
    rgba(1, 16, 31, 0.62);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition:
    transform var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.template-meta__item:hover,
.template-config-grid__item:hover,
.template-field-row:hover {
  transform: translateY(-1px);
  border-color: var(--template-line-strong);
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.08);
}

.template-meta__item strong {
  color: var(--template-text);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 850;
}

.template-config-grid__item--full {
  grid-column: 1 / -1;
}

.template-center :deep(.el-checkbox) {
  --el-checkbox-text-color: rgba(225, 253, 255, 0.82);
  --el-checkbox-checked-text-color: #74f5ff;
  --el-checkbox-checked-bg-color: var(--template-accent);
  --el-checkbox-checked-input-border-color: var(--template-accent);
}

.template-center :deep(.el-segmented) {
  --el-segmented-bg-color: rgba(1, 16, 31, 0.76);
  --el-segmented-item-selected-bg-color: rgba(0, 242, 255, 0.18);
  --el-segmented-item-selected-color: #e1fdff;
  --el-segmented-item-hover-color: #e1fdff;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 8px;
}

.template-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.template-section__title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-section__title strong {
  color: var(--template-text);
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 850;
}

.template-section__title span {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: rgba(116, 245, 255, 0.82);
  font-size: 12px;
  font-weight: 820;
}

.template-section__add {
  min-height: 32px;
  padding: 0 12px;
  border-color: transparent;
  border-radius: 8px;
  background: rgba(0, 242, 255, 0.88);
  color: #00252b;
  font-weight: 850;
}

.template-empty {
  padding: 16px;
  border: 1px dashed rgba(0, 242, 255, 0.2);
  border-radius: 10px;
  color: var(--template-muted);
  background: rgba(1, 16, 31, 0.54);
}

.template-field-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-field-row {
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.055), transparent 58%),
    rgba(1, 16, 31, 0.72);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  transition:
    transform var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.template-field-row__main,
.template-field-row__meta {
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(130px, 1.1fr) minmax(140px, 1.1fr) minmax(112px, 0.8fr) minmax(90px, 0.7fr);
}

.template-field-row__meta {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  margin-top: 10px;
}

.template-field-row__flags,
.template-field-row__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.template-field-row__actions {
  justify-content: flex-end;
}

.template-field-row__actions :deep(.el-button.is-text) {
  color: #74f5ff;
  font-weight: 820;
}

.template-field-row__actions :deep(.el-button.is-text.el-button--danger) {
  color: #ff6b78;
}

@keyframes templateScanline {
  0% { transform: translateX(-45%); opacity: 0.35; }
  50% { opacity: 1; }
  100% { transform: translateX(45%); opacity: 0.35; }
}

@media (max-width: 1180px) {
  .template-center__overview {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .template-center__overview-card.is-workshop {
    grid-column: auto;
  }
}

@media (max-width: 900px) {
  .template-field-row__main,
  .template-field-row__meta {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .template-center__hero {
    align-items: stretch;
    flex-direction: column;
    padding: 16px;
  }

  .template-center__hero-actions {
    min-width: 0;
    align-items: stretch;
    flex-direction: column;
  }

  .template-center__workshop-select,
  .template-center__save {
    width: 100%;
  }

  .template-center__workshop-select {
    flex: 0 0 auto;
  }

  .template-center__overview {
    grid-template-columns: 1fr;
  }

  .template-center__config :deep(.el-card__body),
  .template-center__section :deep(.el-card__body) {
    padding: 12px;
  }

  .template-section__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .template-section__add {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .template-center__hero::after {
    animation: none;
  }

  .template-meta__item,
  .template-config-grid__item,
  .template-field-row {
    transition: none;
  }
}
</style>
