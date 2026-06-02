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
      { label: '长白班', value: 'A' },
      { label: '小夜班', value: 'B' },
      { label: '大夜班', value: 'C' }
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
