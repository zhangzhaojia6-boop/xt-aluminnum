# DynamicEntryForm 模板拆分子组件 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 DynamicEntryForm.vue 模板中的重复字段输入模式和工具面板提取为子组件，消除模板重复，将 SFC 从 1859 行降至 ~1500 行。

**Architecture:** 提取两个子组件：
1. `EntryFieldInput.vue` — 统一的字段输入块（label + OCR badge + input），替换模板中 7+ 处重复
2. `EntryToolsPanel.vue` — review slot 中的工具折叠面板（OCR 记录、前序快照、系统字段、批量粘贴）

**Tech Stack:** Vue 3 SFC, `<script setup>`, Element Plus

**Invariants:**
- 零行为变更——所有 props 和 events 保持原有数据流
- `npm run build` 每个 task 后通过
- 不引入新依赖
- 现有测试继续通过

---

### Task 1: 创建 `EntryFieldInput.vue` 子组件

**Files:**
- Create: `frontend/src/components/mobile/EntryFieldInput.vue`

这个组件封装了模板中重复出现的字段输入模式：label（含必填标记、单位、OCR badge）+ 输入控件（el-input / el-time-picker / textarea）。

- [ ] **Step 1: 创建 `EntryFieldInput.vue`**

```vue
<template>
  <div :class="['mobile-field', wide ? 'mobile-field-wide' : '']">
    <label class="mobile-field-label">
      <span>
        <span v-if="required" class="mobile-required">*</span>
        {{ label }}
        <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
      </span>
      <span
        v-if="ocrMeta"
        :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMeta?.confidence)}`]"
      >
        {{ confidenceLabel(ocrMeta?.confidence) }}
      </span>
    </label>
    <el-time-picker
      v-if="field.type === 'time'"
      :model-value="modelValue"
      value-format="HH:mm:ss"
      format="HH:mm"
      placeholder="选择时间"
      :disabled="disabled"
      class="mobile-time-picker"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <el-input
      v-else
      :model-value="modelValue"
      :type="field.type === 'textarea' ? 'textarea' : 'text'"
      :rows="field.type === 'textarea' ? 3 : undefined"
      :inputmode="field.type === 'number' ? 'decimal' : 'text'"
      :placeholder="placeholder"
      :disabled="disabled"
      @update:model-value="$emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { displayFieldLabel, fieldPlaceholder } from '../../utils/fieldValueHelpers.js'
import { confidenceTone, confidenceLabel } from '../../composables/useOcrState.js'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { default: null },
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  ocrMeta: { type: Object, default: null },
  wide: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const label = computed(() => displayFieldLabel(props.field))
const placeholder = computed(() => fieldPlaceholder(props.field))
</script>
```

- [ ] **Step 2: 验证组件可构建**

Run: `cd frontend && npx vite build`
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/mobile/EntryFieldInput.vue
git commit -m "feat: add EntryFieldInput sub-component for field input pattern"
```

---

### Task 2: 在 DynamicEntryForm.vue 中使用 `EntryFieldInput`

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

替换模板中所有重复的字段输入块。每个替换将 15-20 行缩减为 1 行。

- [ ] **Step 1: 添加 import**

在 DynamicEntryForm.vue 的 `<script setup>` 中添加：
```js
import EntryFieldInput from '../../components/mobile/EntryFieldInput.vue'
```

- [ ] **Step 2: 替换 `#core` slot 中 owner 模式的字段输入块**

将 `#core` slot 中 `v-if="isOwnerOnlyMode"` 分支内的每个字段 div（lines ~212-248）替换为：

```vue
<EntryFieldInput
  v-for="field in section.fields"
  :key="`${section.title}-${field.name}`"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
  :wide="field.name === 'operator_notes'"
/>
```

- [ ] **Step 3: 替换 `#core` slot 中普通模式的字段输入块**

将 `v-else-if="entryFields.length"` 分支内的每个字段 div（lines ~255-292）替换为：

```vue
<EntryFieldInput
  v-for="field in entryFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
  :wide="field.name === 'operator_notes'"
/>
```

- [ ] **Step 4: 替换 `#supplemental` slot 中 owner 模式的字段输入块**

将 owner 模式分支内的字段 div（lines ~317-337）替换为：

```vue
<EntryFieldInput
  v-for="field in section.fields"
  :key="`${section.title}-${field.name}`"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
/>
```

- [ ] **Step 5: 替换 `#supplemental` slot 中 shiftFields 的字段输入块**

将 `v-else-if="shiftFields.length"` 分支内的字段 div（lines ~345-365）替换为：

```vue
<EntryFieldInput
  v-for="field in shiftFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
/>
```

- [ ] **Step 6: 替换 operatorConfirmationFields 的字段输入块**

将 `v-if="operatorConfirmationFields.length"` section 内的字段 div（lines ~372-386）替换为：

```vue
<EntryFieldInput
  v-for="field in operatorConfirmationFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  wide
/>
```

- [ ] **Step 7: 替换 extraFields 的字段输入块**

将 `v-if="extraFields.length"` section 内的字段 div（lines ~393-413）替换为：

```vue
<EntryFieldInput
  v-for="field in extraFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
/>
```

- [ ] **Step 8: 替换 machineFields 的字段输入块**

将 `v-if="machineFields.length"` section 内的字段 div（lines ~420-434）替换为：

```vue
<EntryFieldInput
  v-for="field in machineFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
/>
```

- [ ] **Step 9: 替换 qcFields 的字段输入块**

将 `v-if="qcFields.length"` section 内的字段 div（lines ~441-460）替换为：

```vue
<EntryFieldInput
  v-for="field in qcFields"
  :key="field.name"
  :field="field"
  v-model="formValues[field.name]"
  :disabled="isEntryEditingDisabled"
  :required="isFieldRequired(field)"
  :ocr-meta="ocrMetaForField(field.name)"
/>
```

- [ ] **Step 10: 验证**

Run: `cd frontend && npx vite build`
Expected: clean build.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: replace repeated field input blocks with EntryFieldInput"
```

---

### Task 3: 创建 `EntryToolsPanel.vue` 子组件

**Files:**
- Create: `frontend/src/components/mobile/EntryToolsPanel.vue`

提取 `#review` slot 中的工具折叠面板（OCR 记录、前序快照、系统字段、批量粘贴），约 70 行模板。

- [ ] **Step 1: 创建 `EntryToolsPanel.vue`**

```vue
<template>
  <el-card v-if="hasContent" class="panel mobile-card" data-testid="entry-secondary-sections">
    <template #header>工具与记录</template>
    <el-collapse class="mobile-collapse">
      <el-collapse-item v-if="hasOcrContext" title="拍照记录" name="ocr">
        <div class="mobile-static-grid">
          <div class="mobile-static-chip">
            <span>识别记录</span>
            <strong>#{{ ocrState.submissionId }}</strong>
          </div>
          <div class="mobile-static-chip">
            <span>状态</span>
            <strong>{{ ocrState.verified ? '已核对' : '待核对' }}</strong>
          </div>
        </div>
        <div v-if="ocrState.imageUrl" class="mobile-ocr-preview">
          <img :src="ocrState.imageUrl" alt="识别留存图片">
        </div>
        <div class="mobile-actions">
          <el-button plain @click="$emit('ocr-recapture')">重新拍照</el-button>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="previousStageOutput" title="前序来料快照" name="previous">
        <div class="mobile-history-grid">
          <div>
            <span>来源车间</span>
            <strong>{{ previousStageOutput.workshop || '-' }}</strong>
          </div>
          <div>
            <span>产出重量</span>
            <strong>{{ formatNumber(previousStageOutput.output_weight) }}</strong>
          </div>
          <div>
            <span>产出规格</span>
            <strong>{{ previousStageOutput.output_spec || '-' }}</strong>
          </div>
          <div>
            <span>完成时间</span>
            <strong>{{ formatDateTime(previousStageOutput.completed_at) }}</strong>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="readonlyItems.length" title="系统字段" name="readonly">
        <div class="mobile-static-grid">
          <div v-for="item in readonlyItems" :key="item.name" class="mobile-static-chip">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="showBatchPaste" title="批量粘贴" name="batch">
        <div class="mobile-history-note">制表符分列，每行一卷。</div>
        <div class="mobile-field mobile-field-wide">
          <el-input
            :model-value="batchText"
            type="textarea"
            :rows="6"
            placeholder="示例：批次号〔制表符〕上机重量〔制表符〕下机重量..."
            :disabled="disabled"
            @update:model-value="$emit('update:batchText', $event)"
          />
        </div>
        <div class="mobile-actions">
          <el-button :disabled="disabled" @click="$emit('apply-batch')">载入队列</el-button>
          <div class="mobile-history-note">队列 {{ batchQueueLength }} 卷</div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber, formatDateTime } from '../../utils/display.js'

const props = defineProps({
  ocrState: { type: Object, default: null },
  hasOcrContext: { type: Boolean, default: false },
  previousStageOutput: { type: Object, default: null },
  readonlyItems: { type: Array, default: () => [] },
  showBatchPaste: { type: Boolean, default: false },
  batchText: { type: String, default: '' },
  batchQueueLength: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
})

defineEmits(['ocr-recapture', 'update:batchText', 'apply-batch'])

const hasContent = computed(() =>
  props.hasOcrContext ||
  props.previousStageOutput ||
  props.readonlyItems.length > 0 ||
  props.showBatchPaste
)
</script>
```

- [ ] **Step 2: 验证组件可构建**

Run: `cd frontend && npx vite build`
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/mobile/EntryToolsPanel.vue
git commit -m "feat: add EntryToolsPanel sub-component for review tools"
```

---

### Task 4: 在 DynamicEntryForm.vue 中使用 `EntryToolsPanel`

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

- [ ] **Step 1: 添加 import**

```js
import EntryToolsPanel from '../../components/mobile/EntryToolsPanel.vue'
```

- [ ] **Step 2: 替换 `#review` slot 中的工具面板**

将 `#review` slot 中从 `<el-card v-if="hasSecondaryContent"` 到对应 `</el-card>` 的整个块（约 70 行）替换为：

```vue
<EntryToolsPanel
  :ocr-state="ocrState"
  :has-ocr-context="hasOcrContext"
  :previous-stage-output="currentWorkOrder?.previous_stage_output"
  :readonly-items="readonlyDisplayItems"
  :show-batch-paste="Boolean(template && isFastTempo && !isOwnerOnlyMode)"
  v-model:batch-text="batchText"
  :batch-queue-length="batchQueue.length"
  :disabled="isEntryEditingDisabled"
  @ocr-recapture="goOcrCapture"
  @apply-batch="applyBatchPaste"
/>
```

- [ ] **Step 3: 清理不再需要的 import**

检查 `formatNumber` 和 `formatDateTime` 是否仍在 DynamicEntryForm.vue 中直接使用。如果只在 EntryToolsPanel 中使用，从 DynamicEntryForm.vue 的 import 中移除。

- [ ] **Step 4: 验证**

Run: `cd frontend && npx vite build`
Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: replace review tools section with EntryToolsPanel"
```

---

### Task 5: 最终验证

- [ ] **Step 1: 构建前端**

Run: `cd frontend && npx vite build`
Expected: clean build.

- [ ] **Step 2: 运行后端测试**

Run: `cd backend && python -m pytest -q`
Expected: 502 passed, 0 failed.

- [ ] **Step 3: 统计行数**

Run: `wc -l frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: ~1500 行（从 1859 行降低）。

Run: `wc -l frontend/src/components/mobile/EntryFieldInput.vue frontend/src/components/mobile/EntryToolsPanel.vue`
Expected: EntryFieldInput ~50 行, EntryToolsPanel ~100 行。

- [ ] **Step 4: 确认无遗留重复**

Run: `grep -c "mobile-field-label" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: 0（所有字段 label 已移入 EntryFieldInput）。

- [ ] **Step 5: Commit（如有清理）**

```bash
git add -A
git commit -m "refactor: DynamicEntryForm round 3 template extraction complete"
```
