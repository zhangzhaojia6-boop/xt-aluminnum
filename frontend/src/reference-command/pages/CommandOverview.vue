<template>
  <div class="xt-page command-overview">
    <XtPageHeader title="系统总览主视图" eyebrow="01 OVERVIEW" />
    <XtGrid>
      <XtKpi label="今日产量" value="5,824" unit="吨" trend="+8.6%" />
      <XtKpi label="订单达成率" value="96.7" unit="%" trend="+2.1%" tone="success" />
      <XtKpi label="综合良品率" value="98.2" unit="%" trend="+1.3%" tone="success" />
      <XtKpi label="异常数" value="12" unit="项" trend="待处置" tone="warning" />
    </XtGrid>
    <XtTable title="产线状态" :columns="columns" :rows="rows">
      <template #cell-state="{ value }">
        <XtStatus :value="value === '正常' ? 'success' : 'warning'" :text="value" />
      </template>
    </XtTable>
  </div>
</template>

<script setup>
import { XtGrid, XtKpi, XtPageHeader, XtStatus, XtTable } from '../../components/xt'

const columns = [
  { key: 'name', label: '产线' },
  { key: 'value', label: '产量' },
  { key: 'rate', label: '达成率' },
  { key: 'state', label: '状态' }
]
const rows = [
  { id: 1, name: '铸造一线', value: '1,265', rate: '92.1%', state: '正常' },
  { id: 2, name: '铸造二线', value: '1,132', rate: '94.6%', state: '正常' },
  { id: 3, name: '精整区', value: '986', rate: '91.3%', state: '关注' }
]
</script>

<style scoped>
.command-overview {
  display: grid;
  gap: var(--xt-space-5);
}
</style>
