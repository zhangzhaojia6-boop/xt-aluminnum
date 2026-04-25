<template>
  <CenterPageShell no="01" title="系统总览主视图" data-testid="overview-dashboard">
    <template #tools>
      <span class="status-badge">数据时间 {{ dataTime }}</span>
      <button type="button" class="cmd-button" @click="refresh">刷新</button>
    </template>

    <MockDataNotice source="fallback" message="当前总览使用聚合兜底数据，真实接口接入后保留同一结构。" />
    <KpiStrip aria-label="今日产量 订单达成率 综合成品率 在制产线 异常数 待审核 已交付" :items="reviewOverviewMock.kpis" />

    <div class="center-grid-2">
      <SectionCard title="生产全景" meta="产线状态">
        <DataTableShell :columns="lineColumns" :rows="reviewOverviewMock.lines">
          <template #cell-source="{ row }">
            <SourceBadge :source="row.source" />
          </template>
          <template #cell-status="{ value }">
            <StatusBadge :label="value" :tone="value === '关注' ? 'warning' : 'success'" />
          </template>
        </DataTableShell>
      </SectionCard>

      <SectionCard title="系统状态">
        <div class="action-grid">
          <StatusBadge v-for="item in reviewOverviewMock.system" :key="item.label" :label="`${item.label} ${item.status}`" tone="normal" />
        </div>
      </SectionCard>
    </div>

    <SectionCard title="快捷入口">
      <div class="action-grid">
        <ActionTile label="看板中心" meta="工厂作业" @click="go('factory-dashboard')" />
        <ActionTile label="审单中心" meta="待审任务" @click="go('review-task-center')" />
        <ActionTile label="日报中心" meta="交付清单" @click="go('review-report-center')" />
        <ActionTile label="质量中心" meta="告警处置" @click="go('review-quality-center')" />
        <ActionTile label="成本中心" meta="经营估算" @click="go('review-cost-accounting')" />
        <ActionTile label="AI 总控" meta="辅助提效" @click="go('review-brain-center')" />
      </div>
    </SectionCard>
  </CenterPageShell>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import ActionTile from '../../components/app/ActionTile.vue'
import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { reviewOverviewMock } from '../../mocks/centerMockData.js'

const router = useRouter()
const dataTime = ref('2026-04-24 10:30')

const lineColumns = [
  { key: 'name', label: '产线' },
  { key: 'status', label: '状态' },
  { key: 'source', label: '来源' }
]

function refresh() {
  dataTime.value = new Date().toISOString().slice(0, 16).replace('T', ' ')
}

function go(routeName) {
  router.push({ name: routeName })
}
</script>
