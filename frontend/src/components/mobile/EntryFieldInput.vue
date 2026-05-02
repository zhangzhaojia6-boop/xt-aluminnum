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
      :placeholder="placeholder"
      :disabled="disabled"
      :loading="loadingOptions"
      filterable
      allow-create
      default-first-option
      class="mobile-select"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <el-option
        v-for="option in normalizedOptions"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
    <div v-else-if="field.type === 'spec'" class="mobile-spec-input">
      <el-input
        :model-value="specParts[0]"
        inputmode="decimal"
        placeholder="厚"
        :disabled="disabled"
        @update:model-value="updateSpecPart(0, $event)"
      />
      <span class="mobile-spec-separator">×</span>
      <el-input
        :model-value="specParts[1]"
        inputmode="decimal"
        placeholder="宽"
        :disabled="disabled"
        @update:model-value="updateSpecPart(1, $event)"
      />
      <span class="mobile-spec-separator">×</span>
      <el-input
        :model-value="specParts[2]"
        inputmode="decimal"
        placeholder="长"
        :disabled="disabled"
        @update:model-value="updateSpecPart(2, $event)"
      />
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
import { computed, onMounted, ref, watch } from 'vue'
import { fetchFieldOptions } from '../../api/mobile.js'
import { confidenceLabel, confidenceTone } from '../../composables/useOcrState.js'
import { displayFieldLabel, fieldPlaceholder } from '../../utils/fieldValueHelpers.js'

const optionCache = new Map()

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
const loadingOptions = ref(false)
const selectOptions = ref([])
const normalizedOptions = computed(() =>
  selectOptions.value.map((option) => {
    if (typeof option === 'object' && option !== null) {
      const value = option.value ?? option.label
      return { label: option.label ?? value, value }
    }
    return { label: option, value: option }
  })
)
const specParts = computed(() => splitSpecValue(props.modelValue))

function splitSpecValue(value) {
  const parts = String(value || '')
    .split(/[×xX*]/)
    .map((part) => part.trim())
  return [parts[0] || '', parts[1] || '', parts[2] || '']
}

function formatSpecValue(parts) {
  const cleanParts = parts.map((part) => String(part || '').trim())
  let lastFilledIndex = cleanParts.length - 1
  while (lastFilledIndex >= 0 && !cleanParts[lastFilledIndex]) {
    lastFilledIndex -= 1
  }
  if (lastFilledIndex < 0) return ''
  return cleanParts.slice(0, lastFilledIndex + 1).join('×')
}

function updateSpecPart(index, value) {
  const parts = splitSpecValue(props.modelValue)
  parts[index] = value
  emit('update:modelValue', formatSpecValue(parts))
}

async function loadOptions() {
  const source = props.field.options_source
  if (props.field.type !== 'select' || !source) {
    selectOptions.value = []
    return
  }
  if (optionCache.has(source)) {
    selectOptions.value = optionCache.get(source)
    return
  }
  loadingOptions.value = true
  try {
    const options = await fetchFieldOptions(source)
    selectOptions.value = Array.isArray(options) ? options : []
    optionCache.set(source, selectOptions.value)
  } finally {
    loadingOptions.value = false
  }
}

onMounted(loadOptions)
watch(() => props.field.options_source, loadOptions)
</script>

<style scoped>
.mobile-select {
  width: 100%;
}

.mobile-spec-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.mobile-spec-separator {
  color: rgba(15, 23, 42, 0.42);
  font-weight: 700;
  line-height: 1;
}
</style>
