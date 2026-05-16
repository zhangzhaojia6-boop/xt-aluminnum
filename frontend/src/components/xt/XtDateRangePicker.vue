<template>
  <el-date-picker
    v-model="range"
    type="daterange"
    value-format="YYYY-MM-DD"
    range-separator="至"
    start-placeholder="开始日期"
    end-placeholder="结束日期"
    :shortcuts="shortcuts"
    size="default"
    class="xt-date-range-picker"
  />
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

defineOptions({ name: 'XtDateRangePicker' })

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const range = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val || [])
})

const today = dayjs()
const shortcuts = [
  { text: '今日', value: [today.toDate(), today.toDate()] },
  { text: '昨日', value: [today.subtract(1, 'day').toDate(), today.subtract(1, 'day').toDate()] },
  { text: '本周', value: [today.startOf('week').toDate(), today.toDate()] },
  { text: '本月', value: [today.startOf('month').toDate(), today.toDate()] },
  { text: '本季', value: [today.startOf('quarter').toDate(), today.toDate()] },
  { text: '本年', value: [today.startOf('year').toDate(), today.toDate()] },
  { text: '近7天', value: [today.subtract(6, 'day').toDate(), today.toDate()] },
  { text: '近30天', value: [today.subtract(29, 'day').toDate(), today.toDate()] }
]
</script>

<style scoped>
.xt-date-range-picker {
  font-feature-settings: "tnum";
}
</style>
