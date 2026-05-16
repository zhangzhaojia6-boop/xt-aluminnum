<template>
  <div class="xt-command-bar">
    <div class="xt-command-bar__left">
      <slot name="prefix" />
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :shortcuts="shortcuts"
        size="default"
        @change="onDateChange"
      />
    </div>
    <div class="xt-command-bar__right">
      <slot name="filters" />
      <button v-if="exportable" class="xt-command-bar__export" @click="$emit('export')">
        导出
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import dayjs from 'dayjs'

defineOptions({ name: 'XtCommandBar' })

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  exportable: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'export'])

const dateRange = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const today = dayjs()
const shortcuts = [
  { text: '今日', value: [today.toDate(), today.toDate()] },
  { text: '昨日', value: [today.subtract(1, 'day').toDate(), today.subtract(1, 'day').toDate()] },
  { text: '本周', value: [today.startOf('week').toDate(), today.toDate()] },
  { text: '本月', value: [today.startOf('month').toDate(), today.toDate()] },
  { text: '近7天', value: [today.subtract(6, 'day').toDate(), today.toDate()] },
  { text: '近30天', value: [today.subtract(29, 'day').toDate(), today.toDate()] }
]

function onDateChange(val) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.xt-command-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-3) var(--xt-space-4);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
}

.xt-command-bar__left,
.xt-command-bar__right {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
}

.xt-command-bar__export {
  padding: var(--xt-space-1) var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text-primary);
  font-size: var(--xt-text-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.xt-command-bar__export:hover {
  background: var(--xt-bg-panel-hover);
}
</style>
