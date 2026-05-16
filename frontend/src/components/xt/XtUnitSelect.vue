<template>
  <el-select
    v-model="selected"
    class="xt-unit-select"
    placeholder="单位"
    :disabled="disabled"
    size="default"
  >
    <el-option
      v-for="u in units"
      :key="u.value"
      :label="u.label"
      :value="u.value"
    />
  </el-select>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtUnitSelect' })

const props = defineProps({
  modelValue: {
    type: String,
    default: 'ton'
  },
  units: {
    type: Array,
    default: () => [
      { label: '吨', value: 'ton' },
      { label: '千克', value: 'kg' },
      { label: '米', value: 'm' },
      { label: '件', value: 'pcs' }
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
.xt-unit-select {
  min-width: 80px;
}
</style>
