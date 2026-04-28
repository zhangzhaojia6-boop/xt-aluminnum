<template>
  <div class="xt-page command-module-page">
    <XtPageHeader :title="module.title" :eyebrow="module.moduleId ? `${module.moduleId} MODULE` : 'MODULE'">
      <template #actions>
        <XtExport @export="handleExport" />
      </template>
    </XtPageHeader>

    <XtGrid>
      <XtKpi
        v-for="item in viewModel.kpis"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :unit="item.unit"
        :trend="item.trend"
      />
    </XtGrid>

    <XtTable title="模块数据" :columns="columns" :rows="rows">
      <template #cell-state="{ value }">
        <XtStatus :text="value" :tone="value === '正常' ? 'success' : 'warning'" />
      </template>
    </XtTable>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { XtExport, XtGrid, XtKpi, XtPageHeader, XtStatus, XtTable } from '../../components/xt'
import { adaptModuleView } from '../data/moduleAdapters.js'
import { findModuleById, findModuleByRouteName, referenceModules } from '../data/moduleCatalog.js'

const props = defineProps({
  moduleId: {
    type: String,
    default: ''
  }
})

const route = useRoute()
const module = computed(() => (
  findModuleById(props.moduleId || route.meta?.moduleId)
  || findModuleByRouteName(route.name)
  || referenceModules[0]
))
const viewModel = computed(() => adaptModuleView(module.value.moduleId))
const columns = [
  { key: 'name', label: '对象' },
  { key: 'value', label: '数值' },
  { key: 'rate', label: '达成率' },
  { key: 'state', label: '状态' }
]
const rows = computed(() => viewModel.value.tableRows.map((row, index) => ({ id: index + 1, ...row })))

function handleExport() {}
</script>

<style scoped>
.command-module-page {
  display: grid;
  gap: var(--xt-space-5);
}
</style>
