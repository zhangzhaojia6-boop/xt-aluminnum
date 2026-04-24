<template>
  <el-alert
    class="state-panel"
    :type="type"
    :title="title"
    :description="description"
    show-icon
    :closable="false"
  >
    <template #default>
      <slot />
    </template>
  </el-alert>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'info'
  },
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.state-panel {
  border-radius: 14px;
}
</style>
