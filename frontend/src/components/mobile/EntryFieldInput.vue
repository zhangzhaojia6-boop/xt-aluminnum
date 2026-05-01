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
import { confidenceLabel, confidenceTone } from '../../composables/useOcrState.js'
import { displayFieldLabel, fieldPlaceholder } from '../../utils/fieldValueHelpers.js'

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
