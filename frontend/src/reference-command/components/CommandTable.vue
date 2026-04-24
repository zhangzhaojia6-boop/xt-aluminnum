<template>
  <table class="cmd-table">
    <thead>
      <tr>
        <th v-for="column in resolvedColumns" :key="column.key">{{ column.label }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(row, rowIndex) in rows" :key="row.key || row.name || rowIndex">
        <td v-for="column in resolvedColumns" :key="column.key">
          {{ row[column.key] ?? '—' }}
        </td>
      </tr>
      <tr v-if="rows.length === 0">
        <td :colspan="resolvedColumns.length">暂无数据</td>
      </tr>
    </tbody>
  </table>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  columns: {
    type: Array,
    default: () => []
  },
  rows: {
    type: Array,
    default: () => []
  }
})

const resolvedColumns = computed(() => {
  if (props.columns.length > 0) return props.columns
  return [
    { key: 'name', label: '对象' },
    { key: 'value', label: '数值' },
    { key: 'rate', label: '达成' },
    { key: 'state', label: '状态' }
  ]
})
</script>
