<template>
  <CenterPageShell no="07" title="审阅中心" data-testid="review-task-center">
    <template #tools>
      <StatusBadge label="待审队列" tone="warning" />
      <SourceBadge source="system" />
    </template>

    <MockDataNotice source="fallback" message="审阅任务使用兜底队列，AI 建议仅作为辅助建议。" />
    <KpiStrip :items="taskKpis" />

    <SectionCard title="审阅队列">
      <div class="cmd-review-tabs" role="tablist" aria-label="待审 已审 已驳回" data-review-tabs="待审 已审 已驳回">
        <button v-for="tab in reviewTaskMock.tabs" :key="tab" type="button" role="tab" class="cmd-button">{{ tab }}</button>
      </div>
      <DataTableShell :columns="taskColumns" :rows="reviewTaskMock.rows">
        <template #cell-aiAdvice="{ value }">
          <span>{{ value }}</span>
        </template>
        <template #cell-risk="{ value }">
          <StatusBadge :label="value" :tone="value === '高' ? 'danger' : value === '中' ? 'warning' : 'success'" />
        </template>
        <template #cell-actions>
          <button type="button" class="cmd-mini-button">通过</button>
          <button type="button" class="cmd-mini-button">驳回</button>
        </template>
      </DataTableShell>
    </SectionCard>

    <FixedActionBar>
      <button type="button" class="cmd-button is-primary">批量通过</button>
      <button type="button" class="cmd-button">批量驳回</button>
      <button type="button" class="cmd-button">导出清单</button>
    </FixedActionBar>
  </CenterPageShell>
</template>

<script setup>
import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import FixedActionBar from '../../components/app/FixedActionBar.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { reviewTaskMock } from '../../mocks/centerMockData.js'

const taskKpis = [
  { label: '待审', value: 18, unit: '单', trend: '需确认' },
  { label: '已审', value: 128, unit: '单', trend: '今日累计' },
  { label: '已驳回', value: 7, unit: '单', trend: '待补录' }
]
const taskColumns = [
  { key: 'workshop', label: '录入车间' },
  { key: 'shift', label: '班次' },
  { key: 'submittedAt', label: '提交时间' },
  { key: 'anomalyType', label: '异常类型' },
  { key: 'aiAdvice', label: 'AI 建议' },
  { key: 'risk', label: '风险等级' },
  { key: 'actions', label: '操作' }
]
</script>
