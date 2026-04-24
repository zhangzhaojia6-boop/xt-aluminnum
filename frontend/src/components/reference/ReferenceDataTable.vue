<template>
  <el-table
    v-bind="$attrs"
    :data="data"
    class="reference-data-table"
    size="small"
  >
    <slot />
  </el-table>
</template>

<script setup>
defineOptions({
  inheritAttrs: false
})

defineProps({
  data: {
    type: Array,
    default: () => []
  }
})
</script>
