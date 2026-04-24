<template>
  <div class="cmd-page cmd-module-page" data-module="03" data-testid="mobile-entry">
    <header class="cmd-module-page__head">
      <div class="cmd-module-page__title">
        <span class="cmd-module-page__number">03</span>
        <h1>独立填报终端首页</h1>
      </div>
      <span class="cmd-status" data-testid="mobile-current-shift">当前班次 {{ currentShiftLabel }}</span>
    </header>
    <div class="cmd-module-page__kpis">
      <CommandKpi v-for="kpi in viewModel.kpis" :key="kpi.label" v-bind="kpi" />
    </div>
    <div class="cmd-entry-grid">
      <article class="cmd-entry-card">
        <header class="cmd-entry-card__head"><strong>快捷录入</strong></header>
        <div data-testid="mobile-role-bucket" class="cmd-status">现场直接报数</div>
        <button type="button" class="cmd-button is-primary" data-testid="mobile-go-report" @click="openAdvancedForm">
          快速填报
        </button>
        <CommandActionBar :actions="quickActions" />
      </article>
      <article class="cmd-entry-card">
        <header class="cmd-entry-card__head"><strong>最近状态</strong></header>
        <CommandTable :rows="viewModel.tableRows" />
      </article>
      <article class="cmd-entry-card">
        <header class="cmd-entry-card__head"><strong>任务走势</strong></header>
        <CommandTrend :values="viewModel.trend" />
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import CommandActionBar from '../components/CommandActionBar.vue'
import CommandKpi from '../components/CommandKpi.vue'
import CommandTable from '../components/CommandTable.vue'
import CommandTrend from '../components/CommandTrend.vue'
import { api } from '../../api/index.js'
import { adaptEntryHome } from '../data/moduleAdapters.js'

const router = useRouter()
const currentShift = ref(null)
const viewModel = computed(() => adaptEntryHome())
const currentShiftLabel = computed(() => currentShift.value?.shift_name || currentShift.value?.name || '白班')
const quickActions = [
  { key: 'fill', label: '快速填报', primary: true },
  { key: 'photo', label: '拍照识别' },
  { key: 'history', label: '历史记录' }
]

function resolveShiftParam(key, fallback) {
  return currentShift.value?.[key] || currentShift.value?.current_shift?.[key] || fallback
}

function openAdvancedForm() {
  const businessDate = resolveShiftParam('business_date', new Date().toISOString().slice(0, 10))
  const shiftId = resolveShiftParam('shift_id', 1)
  router.push(`/entry/advanced/${businessDate}/${shiftId}`)
}

onMounted(async () => {
  try {
    const { data } = await api.get('/mobile/current-shift', { skipErrorToast: true })
    currentShift.value = data
  } catch {
    currentShift.value = { shift_name: '白班' }
  }
})
</script>
