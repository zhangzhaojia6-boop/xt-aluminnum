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
    <CenterPageShell
      v-else-if="isReportsModule"
      class="reports-center-page"
      center-no="08"
      title="日报与交付中心"
      data-testid="reports-delivery-center"
    >
      <template #tools>
        <span class="reports-center-page__date">业务日期：{{ reportsData.businessDate }}</span>
        <span class="reports-center-page__updated">更新时间：{{ reportsData.updatedAt }}</span>
        <input
          class="reports-center-page__date-input"
          type="date"
          :value="reportsData.businessDate"
          disabled
          aria-label="业务日期"
          title="日期查询接口待接入，当前只展示本读面数据"
        />
        <button type="button" class="reports-center-page__refresh" @click="refreshReportsView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="reportsData.source !== 'live'"
          :source="reportsData.source"
          message="日报与交付中心使用 fallback 数据，仅用于查看生成、导出与交付状态；不承接生产事实写入。"
        />
      </template>

      <KpiStrip :items="reportsData.kpis" />

      <div class="reports-center-page__overview">
        <SectionCard title="近 7 日日产 / 交付趋势" :meta="reportsData.scope">
          <div class="reports-trend" aria-label="近 7 日日产与交付趋势">
            <div v-for="point in reportsData.trend" :key="point.day" class="reports-trend__item">
              <div class="reports-trend__bars">
                <i
                  class="reports-trend__bar is-output"
                  :style="{ height: `${Math.max(16, Math.round((point.output / reportTrendMax) * 100))}%` }"
                ></i>
                <i
                  class="reports-trend__bar is-delivered"
                  :style="{ height: `${Math.max(10, point.delivered * 3)}%` }"
                ></i>
              </div>
              <strong>{{ point.output.toLocaleString() }}</strong>
              <span>{{ point.day }}</span>
            </div>
          </div>
          <div class="reports-trend__legend">
            <span><i class="is-output"></i>日产量（吨）</span>
            <span><i class="is-delivered"></i>已交付（车）</span>
          </div>
        </SectionCard>

        <SectionCard title="交付摘要" :meta="reportsData.source">
          <div class="reports-delivery-summary">
            <article v-for="item in reportsData.deliverySummary" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }} <small>{{ item.unit }}</small></strong>
              <StatusBadge :label="item.label" :tone="item.tone" />
            </article>
          </div>
        </SectionCard>
      </div>

      <DataTableShell
        data-testid="reports-delivery-table"
        title="交付清单"
        subtitle="日报范围基于 auto_confirmed / 已自动确认数据口径"
        :columns="reportDeliveryColumns"
        :rows="reportsData.deliveryRows"
      >
        <template #cell-name="{ row }">
          <div class="reports-report-name">
            <strong>{{ row.name }}</strong>
            <SourceBadge :source="row.source" />
          </div>
        </template>
        <template #cell-caliber="{ row }">
          <StatusBadge :label="row.caliber" tone="info" />
        </template>
        <template #cell-generationStatus="{ row }">
          <StatusBadge :label="row.generationStatus" :tone="reportStatusTone(row.generationStatus)" />
        </template>
        <template #cell-deliveryStatus="{ row }">
          <StatusBadge :label="row.deliveryStatus" :tone="reportStatusTone(row.deliveryStatus)" />
          <span v-if="row.deliveryStatus === '交付失败'" class="reports-failure-reason">{{ row.reason }}</span>
        </template>
        <template #cell-exportStatus="{ row }">
          <StatusBadge :label="row.exportStatus" :tone="reportStatusTone(row.exportStatus)" />
        </template>
        <template #cell-action="{ row }">
          <button type="button" class="reports-mini-button" disabled :title="row.reason">只读</button>
        </template>
      </DataTableShell>

      <div class="reports-center-page__bottom">
        <SectionCard title="交付操作区" :meta="reportsData.actions.send">
          <div class="reports-action-grid">
            <button type="button" disabled>导出 PDF</button>
            <button type="button" disabled>导出 Excel</button>
            <button type="button" disabled>发送 / 交付</button>
            <button type="button" disabled>重新生成</button>
            <button type="button" @click="showReportPanel('caliber')">查看口径</button>
            <button type="button" @click="showReportPanel('blockers')">查看阻塞项</button>
          </div>
          <p class="reports-action-copy">导出、发送与重新生成接口未接入当前中心读面，按钮保持禁用，不伪造成功状态。</p>
        </SectionCard>

        <SectionCard title="阻塞与风险摘要" :meta="reportsData.source">
          <div class="reports-risk-list">
            <article v-for="blocker in reportsData.blockers" :key="blocker.label">
              <div>
                <span>{{ blocker.label }}</span>
                <strong>{{ blocker.value }}</strong>
              </div>
              <StatusBadge :label="blocker.status" :tone="blocker.tone" />
            </article>
          </div>
          <div class="reports-risk-actions">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-quality-center')">看质量告警</button>
            <button type="button" @click="goRoute('factory-dashboard')">看工厂看板</button>
            <button
              type="button"
              :disabled="!canOpenAdminIngestion"
              :title="canOpenAdminIngestion ? '进入数据接入中心' : '当前账号无管理端权限'"
              @click="goAdminIngestion"
            >
              看数据接入
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard :title="reportInfoPanel === 'blockers' ? '阻塞项说明' : '口径说明'">
        <p v-if="reportInfoPanel === 'blockers'" class="reports-caliber-copy">
          缺报班次、待审记录、异常未关闭与 fallback / mixed 数据源会阻塞日报交付；请优先回到审阅、质量或工厂看板复核。
        </p>
        <p v-else class="reports-caliber-copy">
          日报范围基于已自动确认数据口径（auto_confirmed）生成。当前页面用于查看日报生成、导出与交付状态，不承接生产事实写入。若数据源标记为 fallback/mixed，请以现场试跑口径复核。
        </p>
      </SectionCard>
    </CenterPageShell>
    <CenterPageShell
      v-else-if="isQualityModule"
      class="quality-center-page cmd-layout--quality-alerts"
      center-no="09"
      title="质量与告警中心"
      data-testid="quality-alerts-center"
    >
      <template #tools>
        <span class="quality-center-page__date">业务日期：{{ qualityData.businessDate }}</span>
        <span class="quality-center-page__updated">更新时间：{{ qualityData.updatedAt }}</span>
        <input
          v-model="qualityBusinessDate"
          class="quality-control"
          type="date"
          disabled
          aria-label="业务日期"
          title="日期查询接口待接入，当前只展示本读面数据"
        />
        <select v-model="qualitySeverityFilter" class="quality-control" aria-label="严重度筛选">
          <option value="">全部严重度</option>
          <option value="高">高</option>
          <option value="中">中</option>
          <option value="低">低</option>
        </select>
        <select v-model="qualityStatusFilter" class="quality-control" aria-label="状态筛选">
          <option value="">全部状态</option>
          <option value="待处置">待处置</option>
          <option value="处理中">处理中</option>
          <option value="已处置">已处置</option>
          <option value="已关闭">已关闭</option>
          <option value="阻塞">阻塞</option>
        </select>
        <select v-model="qualitySourceFilter" class="quality-control" aria-label="来源筛选">
          <option value="">全部来源</option>
          <option v-for="source in qualitySourceOptions" :key="source" :value="source">{{ source }}</option>
        </select>
        <button type="button" class="quality-refresh" @click="refreshQualityView">刷新</button>
      </template>

      <template #summary>
        <MockDataNotice
          v-if="qualityData.source !== 'live'"
          :source="qualityData.source"
          message="质量与告警中心使用 fallback 读面数据，仅用于查看告警、处置状态和日报影响；不承接生产事实写入。"
        />
      </template>

      <KpiStrip :items="qualityData.kpis" />

      <div class="quality-center-page__layout">
        <DataTableShell
          data-testid="quality-alert-table"
          title="告警列表"
          subtitle="质量告警来源、严重度、处理状态与日报交付影响"
          :columns="qualityAlertColumns"
          :rows="filteredQualityAlerts"
        >
          <template #actions>
            <StatusBadge label="辅助建议" tone="info" />
          </template>
          <template #cell-source="{ row }">
            <div class="quality-source-cell">
              <strong>{{ row.source }}</strong>
              <SourceBadge :source="row.sourceType" />
            </div>
          </template>
          <template #cell-detail="{ row }">
            <div class="quality-alert-detail">
              <strong>{{ row.detail }}</strong>
              <span>{{ row.reason }}</span>
            </div>
          </template>
          <template #cell-severity="{ row }">
            <StatusBadge :label="row.severity" :tone="qualitySeverityTone(row.severity)" />
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :label="row.status" :tone="qualityStatusTone(row.status)" />
          </template>
          <template #cell-impactScope="{ row }">
            <div class="quality-impact-cell">
              <strong>{{ row.impactScope }}</strong>
              <span>{{ row.deliveryImpact }}</span>
            </div>
          </template>
          <template #cell-action="{ row }">
            <div class="quality-row-actions">
              <button type="button" disabled :title="`详情接口待接入：${row.id}`">查看详情</button>
              <button type="button" disabled title="处置接口待接入，当前不伪造成功状态">标记处理中</button>
              <button type="button" disabled title="关闭接口待接入，AI 不会自动关闭告警">关闭</button>
            </div>
          </template>
        </DataTableShell>

        <aside class="quality-center-page__side">
          <SectionCard title="质量处置流程" :meta="qualityData.source">
            <div class="quality-workflow">
              <article v-for="step in qualityData.workflow" :key="step.title" class="quality-workflow__item">
                <div class="quality-workflow__mark">
                  <strong>{{ step.count }}</strong>
                </div>
                <div>
                  <header>
                    <strong>{{ step.title }}</strong>
                    <StatusBadge :label="step.status" :tone="step.tone" />
                  </header>
                  <p>{{ step.body }}</p>
                  <span>{{ step.nextAction }}</span>
                </div>
              </article>
            </div>
          </SectionCard>

          <SectionCard title="AI 辅助分诊" meta="辅助建议">
            <div class="quality-ai-list">
              <article v-for="item in qualityData.aiTriage" :key="item.label">
                <StatusBadge :label="item.label" :tone="item.tone" />
                <p>{{ item.value }}</p>
              </article>
            </div>
            <p class="quality-helper-copy">AI 只提供辅助建议，不形成最终结论，不自动关闭质量问题。</p>
          </SectionCard>
        </aside>
      </div>

      <div class="quality-center-page__bottom">
        <SectionCard title="操作区" :meta="qualityData.actions.export">
          <div class="quality-action-grid">
            <button type="button" disabled title="详情接口待接入">查看详情</button>
            <button type="button" disabled title="处置接口待接入">标记处理中</button>
            <button type="button" disabled title="关闭接口待接入，AI 不会自动关闭">关闭</button>
            <button type="button" @click="goRoute('review-task-center')">进入审阅任务</button>
            <button type="button" @click="goRoute('review-report-center')">查看日报影响</button>
            <button type="button" disabled title="导出接口待接入">导出告警清单</button>
            <button type="button" disabled title="历史追溯接口待接入">查看历史</button>
          </div>
          <p class="quality-helper-copy">当前只读面不接处置写接口；禁用动作不会伪造“已自动处置成功”。</p>
        </SectionCard>

        <SectionCard title="阻塞与风险摘要" :meta="qualityData.source">
          <div class="quality-blocker-list">
            <article v-for="blocker in qualityData.blockers" :key="blocker.label">
              <div>
                <span>{{ blocker.label }}</span>
                <strong>{{ blocker.value }}</strong>
              </div>
              <StatusBadge :label="blocker.status" :tone="blocker.tone" />
            </article>
          </div>
          <div class="quality-risk-actions">
            <button type="button" @click="goRoute('review-task-center')">去审阅</button>
            <button type="button" @click="goRoute('review-report-center')">看日报</button>
            <button type="button" @click="goRoute('factory-dashboard')">看工厂看板</button>
            <button
              type="button"
              :disabled="!canOpenAdminIngestion"
              :title="canOpenAdminIngestion ? '进入数据接入中心' : '当前账号无管理端权限'"
              @click="goAdminIngestion"
            >
              看数据接入
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="口径说明" :meta="qualityData.source">
        <p class="quality-caliber-copy">{{ qualityData.caliber }}</p>
      </SectionCard>
    </CenterPageShell>
    <CommandPage v-else :module="module" :view-model="viewModel" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { factoryBoardMock, qualityCenterMock, reportsCenterMock } from '../../mocks/centerMockData.js'
import { useAuthStore } from '../../stores/auth.js'
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
const authStore = useAuthStore()
const reportInfoPanel = ref('caliber')
const qualityBusinessDate = ref(qualityCenterMock.businessDate)
const qualitySeverityFilter = ref('')
const qualityStatusFilter = ref('')
const qualitySourceFilter = ref('')

const module = computed(() => (
  findModuleById(props.moduleId || route.meta?.moduleId)
  || findModuleByRouteName(route.name)
  || referenceModules[0]
))

const viewModel = computed(() => adaptModuleView(module.value.moduleId))
const isFactoryModule = computed(() => module.value.moduleId === '05' && route.name !== 'workshop-dashboard')
const isReportsModule = computed(() => module.value.moduleId === '08')
const isQualityModule = computed(() => module.value.moduleId === '09')
const factoryData = factoryBoardMock
const reportsData = reportsCenterMock
const qualityData = qualityCenterMock
const reportTrendMax = computed(() => Math.max(...reportsData.trend.map((point) => point.output), 1))
const canOpenAdminIngestion = computed(() => authStore.adminSurface)

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

const reportDeliveryColumns = [
  { key: 'name', label: '日报名称' },
  { key: 'businessDate', label: '业务日期' },
  { key: 'scopeText', label: '范围 / 车间' },
  { key: 'caliber', label: '生成口径' },
  { key: 'generationStatus', label: '生成状态' },
  { key: 'deliveryStatus', label: '交付状态' },
  { key: 'exportStatus', label: '导出状态' },
  { key: 'receivers', label: '接收对象' },
  { key: 'updatedAt', label: '最近更新时间' },
  { key: 'action', label: '操作' }
]

const qualityAlertColumns = [
  { key: 'time', label: '时间' },
  { key: 'source', label: '来源' },
  { key: 'type', label: '类型' },
  { key: 'detail', label: '描述' },
  { key: 'severity', label: '严重度' },
  { key: 'status', label: '状态' },
  { key: 'impactScope', label: '影响范围' },
  { key: 'owner', label: '责任 / 建议处理人' },
  { key: 'action', label: '操作' }
]

const qualitySourceOptions = computed(() => (
  [...new Set(qualityData.alerts.map((item) => item.source))]
))

const filteredQualityAlerts = computed(() => qualityData.alerts.filter((item) => {
  if (qualitySeverityFilter.value && item.severity !== qualitySeverityFilter.value) return false
  if (qualityStatusFilter.value && item.status !== qualityStatusFilter.value) return false
  if (qualitySourceFilter.value && item.source !== qualitySourceFilter.value) return false
  return true
}))

function goRoute(name) {
  if (route.name !== name) {
    router.push({ name })
  }
}

function refreshFactoryView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshReportsView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function refreshQualityView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function reportStatusTone(value) {
  if (String(value).includes('失败') || String(value).includes('阻塞')) return 'danger'
  if (String(value).includes('待') || String(value).includes('未')) return 'warning'
  if (String(value).includes('已')) return 'success'
  return 'info'
}

function qualitySeverityTone(value) {
  if (value === '高') return 'danger'
  if (value === '中') return 'warning'
  if (value === '低') return 'success'
  return 'info'
}

function qualityStatusTone(value) {
  if (String(value).includes('阻塞')) return 'danger'
  if (String(value).includes('待')) return 'warning'
  if (String(value).includes('处理')) return 'processing'
  if (String(value).includes('关闭')) return 'closed'
  if (String(value).includes('已')) return 'success'
  return 'info'
}

function showReportPanel(panel) {
  reportInfoPanel.value = panel
}

function goAdminIngestion() {
  if (canOpenAdminIngestion.value) {
    goRoute('admin-ingestion-center')
  }
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

.reports-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.reports-center-page)) {
  background: #f5f8fc;
}

.reports-center-page__date,
.reports-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.reports-center-page__date-input,
.reports-center-page__refresh,
.reports-action-grid button,
.reports-risk-actions button,
.reports-mini-button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.reports-center-page__date-input {
  width: 148px;
}

.reports-center-page__refresh,
.reports-action-grid button:not(:disabled),
.reports-risk-actions button:not(:disabled),
.reports-mini-button:not(:disabled) {
  cursor: pointer;
}

.reports-center-page__refresh:hover,
.reports-action-grid button:not(:disabled):hover,
.reports-risk-actions button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.reports-action-grid button:disabled,
.reports-risk-actions button:disabled,
.reports-mini-button:disabled,
.reports-center-page__date-input:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.reports-center-page__overview,
.reports-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.42fr);
  gap: var(--space-card);
  align-items: stretch;
}

.reports-center-page__bottom {
  align-items: start;
}

.reports-trend {
  display: grid;
  grid-template-columns: repeat(7, minmax(54px, 1fr));
  gap: 10px;
  min-height: 190px;
  padding: 12px 8px 2px;
  border-bottom: 1px solid var(--card-border);
}

.reports-trend__item {
  display: grid;
  grid-template-rows: 1fr auto auto;
  gap: 6px;
  min-width: 0;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.reports-trend__bars {
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 5px;
  min-height: 126px;
  border-bottom: 1px dashed var(--card-border);
}

.reports-trend__bar {
  display: block;
  width: 14px;
  min-height: 8px;
  border-radius: 999px 999px 3px 3px;
}

.reports-trend__bar.is-output,
.reports-trend__legend i.is-output {
  background: var(--primary);
}

.reports-trend__bar.is-delivered,
.reports-trend__legend i.is-delivered {
  background: var(--success);
}

.reports-trend__item strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 17px;
  line-height: 1;
}

.reports-trend__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.reports-trend__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.reports-trend__legend i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
}

.reports-delivery-summary,
.reports-risk-list {
  display: grid;
  gap: 10px;
}

.reports-delivery-summary article,
.reports-risk-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  min-height: 52px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.reports-delivery-summary span,
.reports-risk-list span,
.reports-action-copy,
.reports-caliber-copy,
.reports-failure-reason {
  color: var(--text-muted);
  font-size: 12px;
}

.reports-delivery-summary strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 24px;
  line-height: 1;
}

.reports-risk-list strong {
  color: var(--text-main);
  font-size: 15px;
  line-height: 1.35;
  word-break: break-word;
}

.reports-delivery-summary small {
  color: var(--text-muted);
  font-size: 12px;
}

.reports-report-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.reports-report-name strong {
  color: var(--text-main);
  font-weight: 900;
}

.reports-failure-reason {
  display: block;
  margin-top: 5px;
  white-space: normal;
}

.reports-action-grid,
.reports-risk-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.reports-action-grid button,
.reports-risk-actions button {
  width: 100%;
}

.reports-action-copy,
.reports-caliber-copy {
  margin: 0;
  line-height: 1.7;
}

:deep(.reports-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.reports-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.reports-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.reports-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.reports-center-page .section-card),
:deep(.reports-center-page .data-table-shell),
:deep(.reports-center-page .center-page__head),
:deep(.reports-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.reports-center-page .data-table-shell table) {
  min-width: 1120px;
}

:deep(.reports-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.reports-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

.quality-center-page {
  padding: var(--space-page);
}

:global(.cmd-page:has(.quality-center-page)) {
  background: #f5f8fc;
}

.quality-center-page__date,
.quality-center-page__updated {
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.quality-control,
.quality-refresh,
.quality-row-actions button,
.quality-action-grid button,
.quality-risk-actions button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--text-main);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
}

.quality-control {
  max-width: 148px;
}

.quality-refresh,
.quality-action-grid button:not(:disabled),
.quality-risk-actions button:not(:disabled) {
  cursor: pointer;
}

.quality-refresh:hover,
.quality-action-grid button:not(:disabled):hover,
.quality-risk-actions button:not(:disabled):hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
}

.quality-control:disabled,
.quality-row-actions button:disabled,
.quality-action-grid button:disabled,
.quality-risk-actions button:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background: #f8fafc;
}

.quality-center-page__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.42fr);
  gap: var(--space-card);
  align-items: start;
}

.quality-center-page__side,
.quality-workflow,
.quality-ai-list,
.quality-blocker-list {
  display: grid;
  gap: 10px;
}

.quality-source-cell {
  display: grid;
  gap: 5px;
  align-items: start;
}

.quality-source-cell strong,
.quality-impact-cell strong,
.quality-alert-detail strong,
.quality-workflow__item strong,
.quality-blocker-list strong {
  color: var(--text-main);
  font-weight: 900;
}

.quality-alert-detail,
.quality-impact-cell {
  display: grid;
  gap: 5px;
  white-space: normal;
}

.quality-alert-detail span,
.quality-impact-cell span,
.quality-helper-copy,
.quality-caliber-copy,
.quality-workflow__item p,
.quality-workflow__item span,
.quality-ai-list p,
.quality-blocker-list span {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.65;
}

.quality-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 210px;
}

.quality-row-actions button {
  min-height: 30px;
  padding: 0 9px;
  font-size: 12px;
}

.quality-workflow__item {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 12px;
  position: relative;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: #fff;
}

.quality-workflow__item::before {
  content: "";
  position: absolute;
  left: 38px;
  top: 52px;
  bottom: -12px;
  width: 1px;
  border-left: 1px dashed #b8c7da;
}

.quality-workflow__item:last-child::before {
  display: none;
}

.quality-workflow__mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  color: var(--primary);
  background: var(--primary-soft);
  font-family: var(--font-number);
}

.quality-workflow__mark strong {
  color: var(--primary);
  font-size: 25px;
  line-height: 1;
}

.quality-workflow__item header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.quality-workflow__item p,
.quality-ai-list p,
.quality-helper-copy,
.quality-caliber-copy {
  margin: 0;
}

.quality-ai-list article,
.quality-blocker-list article {
  display: grid;
  gap: 7px;
  padding: 10px;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--neutral-soft);
}

.quality-blocker-list article {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.quality-blocker-list article div {
  display: grid;
  gap: 4px;
}

.quality-center-page__bottom {
  display: grid;
  grid-template-columns: minmax(0, 0.86fr) minmax(320px, 1fr);
  gap: var(--space-card);
  align-items: start;
}

.quality-action-grid,
.quality-risk-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.quality-action-grid button,
.quality-risk-actions button {
  width: 100%;
}

:deep(.quality-center-page .kpi-strip) {
  grid-template-columns: repeat(6, minmax(128px, 1fr));
}

:deep(.quality-center-page .kpi-card) {
  min-height: 96px;
  border-radius: 8px;
  box-shadow: none;
}

:deep(.quality-center-page .kpi-card__label) {
  font-size: 13px;
  font-weight: 800;
}

:deep(.quality-center-page .kpi-card__value) {
  font-size: 34px;
}

:deep(.quality-center-page .section-card),
:deep(.quality-center-page .data-table-shell),
:deep(.quality-center-page .center-page__head),
:deep(.quality-center-page .center-page__summary) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.quality-center-page .data-table-shell table) {
  min-width: 1180px;
}

:deep(.quality-center-page .data-table-shell th) {
  font-size: 12px;
}

:deep(.quality-center-page .data-table-shell td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-danger td) {
  background: #fff8f9;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-warning td) {
  background: #fffaf2;
}

:deep(.quality-center-page .data-table-shell tbody tr.is-danger td:first-child) {
  box-shadow: inset 3px 0 0 var(--danger);
}

:deep(.quality-center-page .data-table-shell tbody tr.is-warning td:first-child) {
  box-shadow: inset 3px 0 0 var(--warning);
}

@media (max-width: 1120px) {
  .factory-center-page__layout,
  .factory-caliber-list,
  .reports-center-page__overview,
  .reports-center-page__bottom,
  .quality-center-page__layout,
  .quality-center-page__bottom {
    grid-template-columns: 1fr;
  }

  :deep(.reports-center-page .kpi-strip),
  :deep(.quality-center-page .kpi-strip) {
    grid-template-columns: repeat(3, minmax(160px, 1fr));
  }
}

@media (max-width: 640px) {
  :global(.app-shell:has(.factory-center-page)),
  :global(.app-shell:has(.reports-center-page)),
  :global(.app-shell:has(.quality-center-page)) {
    display: block;
    overflow-x: hidden;
  }

  :global(.app-shell:has(.factory-center-page) > .app-shell__aside),
  :global(.app-shell:has(.factory-center-page) > .el-container),
  :global(.app-shell:has(.factory-center-page) .app-shell__topbar),
  :global(.app-shell:has(.factory-center-page) .app-shell__main),
  :global(.app-shell:has(.reports-center-page) > .app-shell__aside),
  :global(.app-shell:has(.reports-center-page) > .el-container),
  :global(.app-shell:has(.reports-center-page) .app-shell__topbar),
  :global(.app-shell:has(.reports-center-page) .app-shell__main),
  :global(.app-shell:has(.quality-center-page) > .app-shell__aside),
  :global(.app-shell:has(.quality-center-page) > .el-container),
  :global(.app-shell:has(.quality-center-page) .app-shell__topbar),
  :global(.app-shell:has(.quality-center-page) .app-shell__main) {
    width: 100% !important;
  }

  :global(.app-shell:has(.factory-center-page) > .el-container),
  :global(.app-shell:has(.reports-center-page) > .el-container),
  :global(.app-shell:has(.quality-center-page) > .el-container) {
    min-width: 0;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__topbar),
  :global(.app-shell:has(.reports-center-page) .app-shell__topbar),
  :global(.app-shell:has(.quality-center-page) .app-shell__topbar) {
    height: auto;
    flex-wrap: wrap;
    gap: 8px;
  }

  :global(.app-shell:has(.factory-center-page) .app-shell__main),
  :global(.app-shell:has(.reports-center-page) .app-shell__main),
  :global(.app-shell:has(.quality-center-page) .app-shell__main) {
    padding: 8px;
  }

  .factory-center-page,
  .reports-center-page,
  .quality-center-page {
    padding: 10px;
  }

  .factory-risk-actions,
  .reports-action-grid,
  .reports-risk-actions,
  .quality-action-grid,
  .quality-risk-actions,
  :deep(.reports-center-page .kpi-strip),
  :deep(.quality-center-page .kpi-strip) {
    grid-template-columns: 1fr;
  }

  .quality-control {
    max-width: none;
    width: 100%;
  }

  .quality-workflow__item {
    grid-template-columns: 48px minmax(0, 1fr);
  }

  .quality-row-actions {
    min-width: 180px;
  }

  .factory-risk-events span {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .reports-trend {
    grid-template-columns: repeat(7, minmax(48px, 1fr));
    overflow-x: auto;
  }

  .reports-delivery-summary article,
  .reports-risk-list article {
    grid-template-columns: 1fr;
  }
}
</style>
