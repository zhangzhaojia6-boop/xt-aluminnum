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
    <el-select
      v-else-if="field.type === 'select'"
      :model-value="modelValue"
      filterable
      allow-create
      default-first-option
      :placeholder="placeholder"
      :disabled="disabled"
      class="mobile-select"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <el-option v-for="opt in resolvedOptions" :key="opt" :label="opt" :value="opt" />
    </el-select>
    <div v-else-if="field.type === 'spec'" class="mobile-spec-row">
      <el-input
        :model-value="specParts[0]"
        inputmode="decimal"
        placeholder="厚"
        :disabled="disabled"
        class="mobile-spec-input"
        @update:model-value="updateSpecPart(0, $event)"
      />
      <span class="mobile-spec-sep">×</span>
      <el-input
        :model-value="specParts[1]"
        inputmode="decimal"
        placeholder="宽"
        :disabled="disabled"
        class="mobile-spec-input"
        @update:model-value="updateSpecPart(1, $event)"
      />
      <span class="mobile-spec-sep">×</span>
      <el-input
        v-if="!field.spec_suffix"
        :model-value="specParts[2]"
        placeholder="长/C"
        :disabled="disabled"
        class="mobile-spec-input"
        @update:model-value="updateSpecPart(2, $event)"
      />
      <span v-else class="mobile-spec-input mobile-spec-fixed">{{ field.spec_suffix }}</span>
    </div>
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
import { ref, computed, watch, onMounted } from 'vue'
import { confidenceLabel, confidenceTone } from '../../composables/useOcrState.js'
import { displayFieldLabel, fieldPlaceholder } from '../../utils/fieldValueHelpers.js'
import { fetchFieldOptions } from '../../api/mobile.js'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { default: null },
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  ocrMeta: { type: Object, default: null },
  wide: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const label = computed(() => displayFieldLabel(props.field))
const placeholder = computed(() => fieldPlaceholder(props.field))

const dynamicOptions = ref([])
const resolvedOptions = computed(() => {
  if (props.field.options) return props.field.options
  return dynamicOptions.value
})

onMounted(async () => {
  if (props.field.type === 'select' && props.field.options_source) {
    try {
      dynamicOptions.value = await fetchFieldOptions(props.field.options_source)
    } catch { /* fallback to empty */ }
  }
})

function parseSpec(value) {
  const parts = (value || '').split(/[×xX*]/)
  return [parts[0] || '', parts[1] || '', parts[2] || '']
}

const specParts = ref(parseSpec(props.modelValue))

watch(() => props.modelValue, (val) => {
  const parsed = parseSpec(val)
  if (parsed.join('×') !== specParts.value.join('×')) {
    specParts.value = parsed
  }
})

function updateSpecPart(index, value) {
  const parts = [...specParts.value]
  parts[index] = value
  specParts.value = parts
  const suffix = props.field.spec_suffix
  const segments = suffix ? [parts[0], parts[1], suffix] : parts
  emit('update:modelValue', segments.filter(Boolean).join('×'))
}
</script>

<style scoped>
.mobile-select {
  width: 100%;
}

.mobile-spec-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mobile-spec-input {
  flex: 1;
  min-width: 0;
}

.mobile-spec-input :deep(.el-input__inner) {
  text-align: center;
}

.mobile-spec-sep {
  font-size: 16px;
  font-weight: 700;
  color: var(--xt-text-muted);
  flex-shrink: 0;
}

.mobile-spec-fixed {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--xt-bg-page);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  min-height: 32px;
  color: var(--xt-text-secondary);
  font-weight: 700;
  pointer-events: none;
}
</style>
