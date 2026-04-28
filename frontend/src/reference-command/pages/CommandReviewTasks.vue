<template>
  <div class="xt-page command-review-tasks" data-testid="review-task-center">
    <XtPageHeader title="审阅中心" eyebrow="07 REVIEW" />
    <XtGrid>
      <XtKpi label="待审" value="18" unit="单" trend="需确认" tone="warning" />
      <XtKpi label="已审" value="128" unit="单" trend="今日累计" tone="success" />
      <XtKpi label="已驳回" value="7" unit="单" trend="待补录" tone="danger" />
    </XtGrid>
    <XtBatchAction :selected-count="selected.length" :actions="actions" @clear="selected = []" />
    <XtTable title="审阅队列" selectable :columns="columns" :rows="rows" @selection-change="selected = $event">
      <template #cell-risk="{ value }">
        <XtStatus :text="value" :tone="value === '高' ? 'danger' : value === '中' ? 'warning' : 'success'" />
      </template>
      <template #cell-actions>
        <button type="button">通过</button>
      </template>
    </XtTable>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { XtBatchAction, XtGrid, XtKpi, XtPageHeader, XtStatus, XtTable } from '../../components/xt'

const selected = ref([])
const actions = [
  { key: 'approve', label: '批量通过', tone: 'primary' },
  { key: 'reject', label: '批量驳回', tone: 'danger' }
]
const columns = [
  { key: 'workshop', label: '录入车间' },
  { key: 'shift', label: '班次' },
  { key: 'submittedAt', label: '提交时间' },
  { key: 'risk', label: '风险等级' },
  { key: 'actions', label: '操作' }
]
const rows = [
  { id: 1, workshop: '铸造车间', shift: '白班', submittedAt: '10:20', risk: '中' },
  { id: 2, workshop: '精整车间', shift: '夜班', submittedAt: '22:10', risk: '高' }
]
</script>

<style scoped>
.command-review-tasks {
  display: grid;
  gap: var(--xt-space-5);
}

button {
  height: 30px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
}
</style>
