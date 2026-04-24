<template>
  <article class="cmd-panel" :data-module="module.moduleId">
    <header class="cmd-panel__head">
      <div class="cmd-panel__title">
        <span class="cmd-panel__number">{{ module.moduleId }}</span>
        <strong>{{ module.title }}</strong>
      </div>
      <CommandStatus :label="statusLabel" />
    </header>
    <div class="cmd-panel__body">
      <div class="cmd-kpi-grid">
        <CommandKpi
          v-for="kpi in kpis"
          :key="kpi.label"
          v-bind="kpi"
        />
      </div>
      <CommandFlowMap v-if="module.primary?.type === 'flowMap'" />
      <CommandTrend v-else :values="trend" />
      <CommandActionBar :actions="actions" />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

import CommandActionBar from './CommandActionBar.vue'
import CommandFlowMap from './CommandFlowMap.vue'
import CommandKpi from './CommandKpi.vue'
import CommandStatus from './CommandStatus.vue'
import CommandTrend from './CommandTrend.vue'

const props = defineProps({
  module: {
    type: Object,
    required: true
  },
  viewModel: {
    type: Object,
    default: () => ({})
  }
})

const kpis = computed(() => props.viewModel.kpis || [])
const trend = computed(() => props.viewModel.trend || [])
const actions = computed(() => props.viewModel.actions || [])
const statusLabel = computed(() => props.viewModel.statuses?.[0]?.label || '在线')
</script>
