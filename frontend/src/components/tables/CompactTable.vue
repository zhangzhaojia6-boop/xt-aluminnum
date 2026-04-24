<template>
  <div class="compact-table">
    <el-table
      :data="rows"
      stripe
      size="small"
      table-layout="fixed"
      v-bind="$attrs"
    >
      <slot />
    </el-table>
    <div v-if="showEmpty && !rows.length" class="template-empty">{{ emptyText }}</div>
  </div>
</template>

<script setup>
const props = defineProps({
  rows: {
    type: Array,
    default: () => []
  },
  showEmpty: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  }
})
</script>
