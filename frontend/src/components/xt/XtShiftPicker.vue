<template>
  <el-select
    v-model="selected"
    class="xt-shift-picker"
    placeholder="选择班次"
    :disabled="disabled"
    size="default"
  >
    <el-option
      v-for="shift in shifts"
      :key="shift.value"
      :label="shift.label"
      :value="shift.value"
    />
  </el-select>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtShiftPicker' })

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  shifts: {
    type: Array,
    default: () => [
      { label: '白班', value: 'day' },
      { label: '中班', value: 'mid' },
      { label: '夜班', value: 'night' }
    ]
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const selected = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})
</script>

<style scoped>
.xt-shift-picker {
  min-width: 120px;
}
</style>
