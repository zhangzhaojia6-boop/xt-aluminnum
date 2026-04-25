<template>
  <div class="cmd-page">
    <CenterPageShell
      v-if="isFactoryModule"
      class="factory-center-page"
      center-no="05"
      title="工厂作业看板"
      data-testid="factory-dashboard"
    >
      <template #tools>
        <span class="factory-center-page__updated">更新时间：{{ factoryData.updatedAt }}</span>
        <button type="button" class="factory-center-page__refresh" @click="refreshFactoryView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="factoryData.source !== 'live'"
          :source="factoryData.source"
          message="工厂作业看板使用厂级聚合兜底数据，真实读模型接入后替换。"
        />
      </template>

      <KpiStrip :items="factoryData.kpis" />

      <div class="factory-center-page__layout">
        <DataTableShell
          data-testid="factory-line-table"
          title="产线运行明细"
          :columns="factoryColumns"
          :rows="factoryTableRows"
        >
          <template #cell-name="{ row }">
            <div class="factory-line-name" :class="{ 'is-total': row.isTotal }">
              <strong>{{ row.name }}</strong>
              <SourceBadge v-if="row.source" :source="row.source" />
            </div>
          </template>
          <template #cell-output="{ row }">
            <strong class="factory-number">{{ row.output }}</strong>
          </template>
          <template #cell-yieldRate="{ row }">
            <span class="factory-rate">{{ row.yieldRate }}</span>
          </template>
          <template #cell-qualityRate="{ row }">
            <span class="factory-rate">{{ row.qualityRate }}</span>
          </template>
          <template #cell-exceptionCount="{ row }">
            <StatusBadge
              :label="`${row.exceptionCount} 项`"
              :tone="row.exceptionCount > 1 ? 'danger' : row.exceptionCount === 1 ? 'warning' : 'success'"
            />
          </template>
          <template #cell-trend="{ row }">
            <CommandTrend class="factory-sparkline" :values="row.trend" />
          </template>
        </DataTableShell>

        <SectionCard title="风险摘要" class="factory-risk-card">
          <div v-if="factoryData.risks.length" class="factory-risk-list">
            <article v-for="risk in factoryData.risks" :key="risk.label" class="factory-risk-item">
              <div>
                <span>{{ risk.label }}</span>
                <strong>{{ risk.value }}</strong>
              </div>
              <StatusBadge :label="risk.status" :tone="risk.tone" />
            </article>
          </div>
          <div v-else class="factory-empty-state">暂无风险摘要</div>

          <div class="factory-risk-events">
            <strong>最近风险事件</strong>
            <span v-for="event in factoryData.events" :key="event.time">
              <SourceBadge :source="event.source" />
              <em>{{ event.time }}</em>
              {{ event.text }}
            </span>
          </div>

          <div class="factory-risk-actions" aria-label="风险处置入口">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-quality-center')">看质量告警</button>
            <button type="button" @click="goRoute('review-report-center')">查看日报</button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="来源与口径" class="factory-caliber-card">
        <div class="factory-caliber-list">
          <span v-for="item in factoryData.caliber" :key="item">{{ item }}</span>
        </div>
      </SectionCard>
    </CenterPageShell>
    <CommandPage v-else :module="module" :view-model="viewModel" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { factoryBoardMock } from '../../mocks/centerMockData.js'
import CommandPage from '../components/CommandPage.vue'
import CommandTrend from '../components/CommandTrend.vue'
import { adaptModuleView } from '../data/moduleAdapters.js'
import { findModuleById, findModuleByRouteName, referenceModules } from '../data/moduleCatalog.js'

const props = defineProps({
  moduleId: {
    type: String,
    default: ''
  }
})

const route = useRoute()
const router = useRouter()

const module = computed(() => (
  findModuleById(props.moduleId || route.meta?.moduleId)
  || findModuleByRouteName(route.name)
  || referenceModules[0]
))

const viewModel = computed(() => adaptModuleView(module.value.moduleId))
const isFactoryModule = computed(() => module.value.moduleId === '05' && route.name !== 'workshop-dashboard')
const factoryData = factoryBoardMock

const factoryColumns = [
  { key: 'name', label: '车间 / 产线' },
  { key: 'output', label: '产量（吨）' },
  { key: 'yieldRate', label: '成品率' },
  { key: 'qualityRate', label: '良率 / 优品率' },
  { key: 'exceptionCount', label: '异常' },
  { key: 'trend', label: '趋势（24h）' }
]

const factoryTableRows = computed(() => [
  ...factoryData.rows,
  {
    ...factoryData.total,
    id: 'factory-total',
    isTotal: true
  }
])

function goRoute(name) {
  if (route.name !== name) {
    router.push({ name })
  }
}

function refreshFactoryView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}
</script>

<style scoped>
.factory-center-page {
  padding: var(--space-page);
}

.factory-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.factory-center-page__refresh,
.factory-risk-actions button {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  color: var(--text-main);
  background: #fff;
  font-weight: 800;
  cursor: pointer;
}

.factory-center-page__refresh:hover,
.factory-risk-actions button:hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.factory-center-page__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  gap: var(--space-card);
  align-items: start;
}

.factory-line-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.factory-line-name strong,
.factory-number,
.factory-rate {
  color: var(--text-main);
  font-weight: 900;
}

.factory-number,
.factory-rate {
  font-family: var(--font-number);
  font-size: 18px;
}

.factory-sparkline {
  width: 108px;
  height: 34px;
}

.factory-risk-card {
  min-height: 100%;
}

.factory-risk-list,
.factory-risk-events,
.factory-risk-actions,
.factory-caliber-list {
  display: grid;
  gap: 9px;
}

.factory-risk-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  background: var(--neutral-soft);
}

.factory-risk-item div {
  display: grid;
  gap: 3px;
}

.factory-risk-item span,
.factory-risk-events em,
.factory-caliber-list span,
.factory-empty-state {
  color: var(--text-muted);
  font-size: 12px;
  font-style: normal;
}

.factory-risk-item strong {
  color: var(--text-main);
  font-size: 14px;
}

.factory-risk-events {
  padding-top: 4px;
}

.factory-risk-events strong {
  color: var(--text-main);
  font-size: 13px;
}

.factory-risk-events span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.factory-risk-actions {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.factory-risk-actions button {
  width: 100%;
}

.factory-caliber-list {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.factory-caliber-list span {
  padding: 9px 10px;
  border: 1px solid var(--card-border);
  border-radius: var(--radius-control);
  background: var(--neutral-soft);
}

:deep(.factory-center-page .data-table-shell table) {
  min-width: 760px;
}

:deep(.factory-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.factory-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: middle;
}

:deep(.factory-center-page .data-table-shell tbody tr:last-child td) {
  border-top: 1px solid var(--primary-soft);
  background: #f7faff;
}

@media (max-width: 1120px) {
  .factory-center-page__layout,
  .factory-caliber-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  :global(.app-shell:has(.factory-center-page)) {
    display: block;
    overflow-x: hidden;
  }

  :global(.app-shell:has(.factory-center-page) > .app-shell__aside),
  :global(.app-shell:has(.factory-center-page) > .el-container),
  :global(.app-shell:has(.factory-center-page) .app-shell__topbar),
  :global(.app-shell:has(.factory-center-page) .app-shell__main) {
    width: 100% !important;
  }

  :global(.app-shell:has(.factory-center-page) > .el-container) {
    min-width: 0;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__topbar) {
    height: auto;
    flex-wrap: wrap;
    gap: 8px;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__main) {
    padding: 8px;
  }

  .factory-center-page {
    padding: 10px;
  }

  .factory-risk-actions {
    grid-template-columns: 1fr;
  }

  .factory-risk-events span {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
