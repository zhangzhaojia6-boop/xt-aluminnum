<template>
  <section class="cmd-canvas">
    <div class="cmd-canvas__grid">
      <CommandPanel
        v-for="module in modules"
        :key="module.moduleId"
        :module="module"
        :view-model="viewModels[module.moduleId] || fallbackViewModel"
      />
    </div>
  </section>
</template>

<script setup>
import CommandPanel from './CommandPanel.vue'
import { referenceModules } from '../data/moduleCatalog.js'

defineProps({
  modules: {
    type: Array,
    default: () => referenceModules
  },
  viewModels: {
    type: Object,
    default: () => ({})
  }
})

const fallbackViewModel = {
  kpis: [
    { label: '产量', value: '5,824', unit: '吨', trend: '+8.6%', icon: '产' },
    { label: '良率', value: '98.2', unit: '%', trend: '+1.3%', icon: '质' },
    { label: '异常', value: '12', unit: '项', trend: '待处置', icon: '异' }
  ],
  trend: [18, 24, 21, 33, 29, 36, 41, 35],
  actions: [{ key: 'open', label: '进入', primary: true }],
  statuses: [{ label: '在线', state: 'normal' }]
}
</script>
