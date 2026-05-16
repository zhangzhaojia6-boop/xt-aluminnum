<template>
  <div class="xt-numeric-input">
    <input
      ref="inputRef"
      type="text"
      inputmode="decimal"
      class="xt-numeric-input__field"
      :value="displayValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
      @blur="onBlur"
    />
    <span v-if="unit" class="xt-numeric-input__unit">{{ unit }}</span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

defineOptions({ name: 'XtNumericInput' })

const props = defineProps({
  modelValue: {
    type: Number,
    default: null
  },
  unit: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  precision: {
    type: Number,
    default: 2
  },
  min: {
    type: Number,
    default: -Infinity
  },
  max: {
    type: Number,
    default: Infinity
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])
const inputRef = ref(null)

const displayValue = computed(() => {
  if (props.modelValue === null || props.modelValue === undefined) return ''
  return String(props.modelValue)
})

function onInput(e) {
  const raw = e.target.value.replace(/[^\d.\-]/g, '')
  e.target.value = raw
  const num = parseFloat(raw)
  if (!isNaN(num)) {
    const clamped = Math.min(props.max, Math.max(props.min, num))
    emit('update:modelValue', clamped)
  } else if (raw === '' || raw === '-') {
    emit('update:modelValue', null)
  }
}

function onBlur() {
  if (props.modelValue !== null && props.modelValue !== undefined) {
    const rounded = Number(props.modelValue.toFixed(props.precision))
    emit('update:modelValue', rounded)
  }
}
</script>

<style scoped>
.xt-numeric-input {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  overflow: hidden;
}

.xt-numeric-input__field {
  flex: 1;
  min-width: 0;
  padding: var(--xt-space-2) var(--xt-space-3);
  border: none;
  background: transparent;
  color: var(--xt-text-primary);
  font-size: var(--xt-text-sm);
  font-feature-settings: "tnum";
  outline: none;
}

.xt-numeric-input__field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.xt-numeric-input__unit {
  padding: var(--xt-space-2) var(--xt-space-3);
  background: var(--xt-bg-panel-soft);
  border-left: 1px solid var(--xt-border-light);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  white-space: nowrap;
}
</style>
