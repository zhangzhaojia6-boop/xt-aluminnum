<template>
  <section
    class="cmd-module-page reference-page"
    :class="pageCompatClass"
    :data-module="module.moduleId"
    :data-testid="pageTestId"
  >
    <header class="cmd-module-page__head">
      <div class="cmd-module-page__title">
        <span class="cmd-module-page__number">{{ module.moduleId }}</span>
        <h1>{{ moduleTitle }}</h1>
      </div>
      <CommandStatus :label="statusLabel" />
    </header>

    <section v-if="showFactoryCompat" class="cmd-factory-board" data-testid="review-home-hero">
      <div class="cmd-factory-board__top">
        <span class="cmd-factory-board__lead">厂级观察面 · 不写入生产事实</span>
        <div class="cmd-factory-board__badges">
          <span class="cmd-muted">更新时间：{{ factoryBoardMock.updatedAt }}</span>
          <button type="button" role="tab" class="cmd-button" @click="refreshView">刷新</button>
          <span class="cmd-status" data-testid="delivery-ready-card">日报交付就绪</span>
          <span class="cmd-status" data-testid="delivery-missing-steps">待补齐步骤</span>
        </div>
      </div>

      <MockDataNotice source="fallback" message="工厂作业看板使用兜底状态网格，真实接口接入后替换。" />

      <div data-testid="review-command-deck" class="cmd-factory-board__main">
        <table class="cmd-table cmd-factory-table">
          <thead>
            <tr>
              <th>车间/产线</th>
              <th>产量（吨）</th>
              <th>成品率</th>
              <th>良率/优品率</th>
              <th>异常</th>
              <th>趋势（24h）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in factoryRows" :key="row.name">
              <td>{{ row.name }}</td>
              <td>{{ row.output }}</td>
              <td>{{ row.yieldRate }}</td>
              <td>{{ row.qualityRate }}</td>
              <td :class="{ 'is-risk': row.exceptionCount > 0 }">{{ row.exceptionCount }}</td>
              <td><CommandTrend :values="row.trend" /></td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>{{ factoryBoardMock.total.name }}</td>
              <td>{{ factoryBoardMock.total.output }}</td>
              <td>{{ factoryBoardMock.total.yieldRate }}</td>
              <td>{{ factoryBoardMock.total.qualityRate }}</td>
              <td class="is-risk">{{ factoryBoardMock.total.exceptionCount }}</td>
              <td><CommandTrend :values="[8, 12, 10, 15, 13, 16, 14]" /></td>
            </tr>
          </tfoot>
        </table>

        <aside class="cmd-factory-board__side">
          <div class="cmd-risk-summary" aria-label="风险摘要">
            <strong>风险摘要</strong>
            <span v-for="risk in factoryBoardMock.risks" :key="risk.label">
              <StatusBadge :label="risk.label" :tone="risk.tone" />
              <em>{{ risk.value }}</em>
            </span>
            <button type="button" class="cmd-button" @click="goRoute('review-task-center')">进入审阅任务</button>
            <button type="button" class="cmd-button" @click="goRoute('review-quality-center')">进入质量中心</button>
          </div>
          <div data-testid="agent-runtime-flow" class="cmd-factory-ai">
            <strong>系统辅助状态</strong>
            <span>分析决策助手</span>
            <span>执行交付助手</span>
            <span>可靠度</span>
            <span>风险级别</span>
            <span>阻塞项</span>
            <span>异常数</span>
            <span class="panel-source-tag">算法流水线 · 确定性规则</span>
            <span class="panel-source-tag">分析决策助手 · 解释与建议</span>
            <span class="panel-source-tag">执行交付助手 · 闭环执行</span>
          </div>
          <div data-testid="review-assistant-dock" class="cmd-action-bar">
            <button type="button" class="is-primary" @click="assistantOpen = true">打开 AI 助手</button>
            <button type="button" class="review-factory-detail-toggle__btn">展开运行详情</button>
          </div>
        </aside>
      </div>

      <div v-if="assistantOpen" data-testid="review-assistant-workbench" class="cmd-factory-workbench review-assistant-workbench__capability-top">
        <h3>问答</h3>
        <h3>取数</h3>
        <h3>图卡</h3>
        <button type="button" class="cmd-button">开始问答</button>
        <button type="button" class="cmd-button">搜上下文</button>
        <button type="button" class="cmd-button">出图</button>
      </div>
    </section>

    <template v-else>
      <div v-if="module.moduleId === '13'" data-testid="review-governance-center" class="cmd-status">权限治理在线</div>
      <div v-if="module.moduleId === '13'" data-testid="admin-users-center" class="cmd-status">用户治理在线</div>
      <div v-if="module.moduleId === '14'" data-testid="admin-home" class="cmd-status">管理总览在线</div>
      <div v-if="module.moduleId === '14'" data-testid="admin-master-center" class="cmd-status">主数据在线</div>
      <div v-if="module.moduleId === '14'" data-testid="template-editor-page" class="cmd-status">模板中心在线</div>

      <MockDataNotice v-if="showModuleFallbackNotice" source="fallback" :message="moduleFallbackNotice" />

      <section :class="['cmd-target-layout', layoutClass]">
        <template v-if="module.moduleId === '06'">
          <div class="cmd-module-page__primary cmd-ingestion-grid">
            <section class="cmd-ingestion-sources">
              <header class="cmd-section-title">数据源列表</header>
              <div class="cmd-source-list">
                <span v-for="source in ingestionCenterMock.sources" :key="source.name">
                  <SourceBadge :source="source.source" />
                  {{ source.name }}
                  <StatusBadge :label="source.status" :tone="source.tone" />
                </span>
              </div>
              <button type="button" class="cmd-button" disabled title="待接入真实新增数据源接口">添加数据源（待接入）</button>
            </section>

            <section class="cmd-ingestion-mapping">
              <header class="cmd-section-title">字段映射</header>
              <table class="cmd-table">
                <thead><tr><th>字段名称</th><th>字段类型</th><th>数据源字段</th><th>映射方式</th><th>校验状态</th></tr></thead>
                <tbody>
                  <tr v-for="row in ingestionCenterMock.fields" :key="row.name">
                    <td>{{ row.name }}</td>
                    <td><StatusBadge :label="row.type" tone="info" /></td>
                    <td>{{ row.sourceField }}</td>
                    <td>{{ row.mapping }}</td>
                    <td><StatusBadge :label="row.check" tone="success" /></td>
                  </tr>
                </tbody>
              </table>
              <button type="button" class="cmd-button" disabled title="映射保存接口待接入">编辑映射规则（待接入）</button>
            </section>

            <section class="cmd-ingestion-history">
              <header class="cmd-section-title">导入历史（最近）</header>
              <table class="cmd-table">
                <thead><tr><th>时间</th><th>数据源</th><th>文件/任务名称</th><th>总行数</th><th>成功行数</th><th>失败行数</th><th>状态</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in ingestionCenterMock.history" :key="row.id">
                    <td>{{ row.time }}</td>
                    <td>{{ row.source }}</td>
                    <td>{{ row.task }}</td>
                    <td>{{ row.total }}</td>
                    <td>{{ row.success }}</td>
                    <td :class="{ 'is-risk': row.failed !== '0' }">{{ row.failed }}</td>
                    <td><StatusBadge :label="row.status" :tone="row.status === '部分失败' ? 'warning' : 'success'" /></td>
                    <td><button type="button" class="cmd-mini-button" disabled :title="row.reason">详情（待接入）</button></td>
                  </tr>
                </tbody>
              </table>
            </section>
          </div>
          <aside class="cmd-module-page__side cmd-ingestion-side">
            <strong>导入概览（今日）</strong>
            <div v-for="item in ingestionCenterMock.overview" :key="item.label" class="cmd-side-metric">
              <span>{{ item.label }}</span>
              <b :class="`is-${item.tone}`">{{ item.value }}<small>{{ item.unit }}</small></b>
            </div>
            <div class="cmd-donut" aria-label="导入成功率">88.54%</div>
            <strong>错误/失败说明</strong>
            <span class="cmd-muted">失败记录可进入历史行查看原因摘要；详情接口待接入，不伪造成功处理。</span>
          </aside>
        </template>

        <template v-else-if="showReviewTasks">
          <MockDataNotice source="fallback" message="审阅任务使用兜底队列，AI 建议仅作为辅助建议。" />
          <div class="cmd-review-tabs" role="tablist" aria-label="待审 已审 已驳回" data-review-tabs="待审 已审 已驳回">
            <button v-for="tab in reviewTaskMock.tabs" :key="tab" type="button" role="tab" class="cmd-button">{{ tab }}</button>
          </div>
          <table class="cmd-table cmd-module-page__primary">
            <thead><tr><th>录入车间</th><th>班次</th><th>提交时间</th><th>异常类型</th><th>AI 建议</th><th>风险等级</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="row in reviewTaskMock.rows" :key="row.id">
                <td>{{ row.workshop }}</td><td>{{ row.shift }}</td><td>{{ row.submittedAt }}</td><td>{{ row.anomalyType }}</td><td>{{ row.aiAdvice }}</td><td>{{ row.risk }}</td>
                <td><button type="button" class="cmd-mini-button">通过</button><button type="button" class="cmd-mini-button">驳回</button></td>
              </tr>
            </tbody>
          </table>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>批量操作</strong>
            <button type="button" class="cmd-button is-primary">批量通过</button>
            <button type="button" class="cmd-button">批量驳回</button>
            <button type="button" class="cmd-button">导出清单</button>
            <CommandTrend :values="viewModel.trend" />
          </aside>
        </template>

        <template v-else-if="module.moduleId === '08'">
          <div class="cmd-module-page__primary cmd-report-center">
            <KpiStrip :items="reportDeliveryMock.kpis" />
            <section class="cmd-chart-card">
              <header class="cmd-section-title">日量趋势</header>
              <CommandTrend class="cmd-wide-trend" :values="reportDeliveryMock.trend" />
              <span class="cmd-muted">日报范围：auto_confirmed / 已自动确认口径。</span>
            </section>
          </div>
          <aside class="cmd-module-page__side cmd-delivery-list cmd-delivery-panel">
            <strong>交付清单</strong>
            <span v-for="item in reportDeliveryMock.delivery" :key="item.label">
              {{ item.label }} <b>{{ item.value }} {{ item.unit }}</b>
              <StatusBadge :label="item.tone === 'danger' ? '阻塞' : '状态'" :tone="item.tone" />
            </span>
            <strong>操作区</strong>
            <button
              v-for="action in reportDeliveryMock.actions"
              :key="action.label"
              type="button"
              class="cmd-button"
              :disabled="action.state !== '可用'"
              :title="action.state === '可用' ? '仅导出当前日报视图' : '后端交付接口待接入'"
            >
              {{ action.label }}{{ action.state === '可用' ? '' : '（待接入）' }}
            </button>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '09'">
          <table class="cmd-table cmd-module-page__primary">
            <thead><tr><th>时间</th><th>来源</th><th>类型</th><th>描述</th><th>严重度</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="row in qualityCenterMock.rows" :key="row.id">
                <td>{{ row.time }}</td>
                <td>{{ row.source }}</td>
                <td>{{ row.type }}</td>
                <td>{{ row.detail }}</td>
                <td><StatusBadge :label="row.severity" :tone="severityTone(row.severity)" /></td>
                <td><StatusBadge :label="row.status" :tone="qualityStatusTone(row.status)" /></td>
                <td>
                  <button type="button" class="cmd-mini-button" disabled title="详情接口待接入">查看详情</button>
                  <button type="button" class="cmd-mini-button" disabled title="处置接口待接入">标记处理中</button>
                  <button type="button" class="cmd-mini-button" disabled title="关闭接口待接入">关闭</button>
                </td>
              </tr>
            </tbody>
          </table>
          <aside class="cmd-module-page__side cmd-stack-list cmd-quality-flow">
            <strong>质量处置流程</strong>
            <span v-for="step in qualityCenterMock.flow" :key="step.title">
              <b>{{ step.title }}</b>
              <em>{{ step.body }}</em>
            </span>
            <button type="button" class="cmd-button" @click="goRoute('review-task-center')">进入审阅任务</button>
            <span class="cmd-muted">AI 辅助分诊仅作辅助建议，不自动关闭质量问题。</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '10'">
          <div class="cmd-module-page__primary cmd-cost-center">
            <div class="cmd-tab-row">
              <button v-for="tab in costCenterMock.caliberTabs" :key="tab" type="button" class="cmd-button" :class="{ 'is-primary': tab === '铸二' }">{{ tab }}</button>
            </div>
            <div class="cmd-tab-row">
              <button type="button" class="cmd-button is-primary">产量口径</button>
              <button type="button" class="cmd-button" disabled title="通货口径策略接口待接入">通货口径（待接入）</button>
            </div>
            <KpiStrip :items="costCenterMock.kpis" />
            <section class="cmd-chart-card">
              <header class="cmd-section-title">成本构成趋势（元/吨）</header>
              <div class="cmd-stack-chart">
                <div v-for="bar in costCenterMock.trend" :key="bar.day" class="cmd-stack-bar">
                  <i
                    v-for="(part, index) in bar.parts"
                    :key="`${bar.day}-${index}`"
                    :style="{ height: `${part / 90}%` }"
                    :class="`is-part-${index}`"
                  ></i>
                  <span>{{ bar.day }}</span>
                </div>
              </div>
            </section>
          </div>
          <aside class="cmd-module-page__side cmd-stack-list cmd-cost-summary">
            <strong>经营估算 / 策略口径</strong>
            <span v-for="row in costCenterMock.cumulative" :key="row.label" :class="{ 'is-total': row.label === '合计' }">
              <b>{{ row.label }}</b>
              <em>{{ row.value }}</em>
              <strong>{{ row.ratio }}</strong>
            </span>
            <button type="button" class="cmd-button" disabled title="当前仅展示只读策略口径说明">调整方案（待接入）</button>
            <button type="button" class="cmd-button" disabled title="口径抽屉待接入">查看口径（待接入）</button>
            <button type="button" class="cmd-button" disabled title="导出接口待接入">导出（待接入）</button>
            <span class="cmd-muted">本页不是财务结算中心，不显示财务月结结果。</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '11'">
          <div class="cmd-module-page__primary cmd-ai-grid">
            <article v-for="item in brainRisks" :key="item.title">
              <strong>{{ item.title }}</strong>
              <span>{{ item.value }}</span>
            </article>
          </div>
          <aside class="cmd-module-page__side cmd-assistant-card">
            <strong>智能助手</strong>
            <p>今日异常优先看待补卡与质量波动。</p>
            <button type="button" class="cmd-button is-primary">发送问题</button>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '12'">
          <div class="cmd-module-page__primary cmd-ops-grid">
            <article class="stat-card"><span>可用率</span><strong class="stat-value">99.6%</strong></article>
            <article class="stat-card"><span>响应耗时</span><strong class="stat-value">218ms</strong></article>
            <div class="cmd-ops-timeline"><i v-for="item in opsTimeline" :key="item"></i></div>
          </div>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>实时探针</strong>
            <span v-for="service in opsServices" :key="service">{{ service }}</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '13'">
          <table class="cmd-table cmd-module-page__primary">
            <thead><tr><th>角色</th><th>看板</th><th>填报</th><th>审阅</th><th>主数据</th><th>导出</th></tr></thead>
            <tbody>
              <tr v-for="row in governanceRows" :key="row.role">
                <td>{{ row.role }}</td><td>✓</td><td>{{ row.entry }}</td><td>{{ row.review }}</td><td>{{ row.master }}</td><td>{{ row.export }}</td>
              </tr>
            </tbody>
          </table>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>质量审计日志</strong>
            <span>05-21 李四 修改角色配置</span><span>05-21 王五 导出日报</span><span>05-21 赵六 查看模板</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '14'">
          <div class="cmd-module-page__primary cmd-tile-grid">
            <article v-for="tile in masterTiles" :key="tile.label">
              <strong>{{ tile.icon }}</strong><span>{{ tile.label }}</span><em>{{ tile.value }}</em>
            </article>
          </div>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>模板审计日志</strong>
            <span>车间模板更新</span><span>字段映射调整</span><span>用户组同步</span>
          </aside>
        </template>

        <template v-else>
          <div class="cmd-module-page__kpis">
            <CommandKpi v-for="kpi in viewModel.kpis" :key="kpi.label" v-bind="kpi" />
          </div>
          <div class="cmd-module-page__body">
            <main class="cmd-module-page__primary">
              <CommandFlowMap v-if="module.primary?.type === 'flowMap'" />
              <CommandTrend v-else-if="module.primary?.type === 'trend'" :values="viewModel.trend" />
              <CommandTable v-else :rows="viewModel.tableRows" />
            </main>
            <aside class="cmd-module-page__side">
              <div v-for="risk in viewModel.risks" :key="risk.text" class="cmd-side-row">
                <CommandStatus :label="`${risk.level} ${risk.text}`" />
              </div>
              <CommandTrend :values="viewModel.trend" />
            </aside>
          </div>
        </template>
      </section>

      <CommandActionBar :actions="viewModel.actions" />
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CommandActionBar from './CommandActionBar.vue'
import CommandFlowMap from './CommandFlowMap.vue'
import CommandKpi from './CommandKpi.vue'
import CommandStatus from './CommandStatus.vue'
import CommandTable from './CommandTable.vue'
import CommandTrend from './CommandTrend.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import {
  costCenterMock,
  factoryBoardMock,
  ingestionCenterMock,
  qualityCenterMock,
  reportDeliveryMock,
  reviewTaskMock
} from '../../mocks/centerMockData.js'

const props = defineProps({
  module: {
    type: Object,
    required: true
  },
  viewModel: {
    type: Object,
    required: true
  }
})

const route = useRoute()
const router = useRouter()
const assistantOpen = ref(false)

const statusLabel = computed(() => props.viewModel.statuses?.[0]?.label || '在线')
const showFactoryCompat = computed(() => props.module.moduleId === '05' && route.name !== 'workshop-dashboard')
const showReviewTasks = computed(() => props.module.moduleId === '07')
const showModuleFallbackNotice = computed(() => ['06', '08', '09', '10', '11', '12', '13', '14'].includes(props.module.moduleId))
const moduleFallbackNotice = computed(() => (
  {
    '06': '数据接入中心使用兜底接入与映射数据，不作为生产事实补录入口。',
    '10': '成本中心使用经营估算 / 策略口径兜底数据，不代表财务结算。',
    '11': 'AI 总控使用兜底摘要，AI 建议仅作为辅助建议。'
  }[props.module.moduleId] || '中心页使用兜底数据，真实接口接入后替换。'
))
const moduleTitle = computed(() => route.name === 'workshop-dashboard' ? '车间审阅端' : props.module.title)
const layoutClassMap = {
  'mapping-center': 'cmd-layout--mapping-center',
  'table-with-side-risk': 'cmd-layout--review-center',
  'report-delivery': 'cmd-layout--report-delivery',
  'quality-alerts': 'cmd-layout--quality-alerts',
  'cost-stack': 'cmd-layout--cost-stack',
  'ai-brain': 'cmd-layout--ai-brain',
  'ops-observability': 'cmd-layout--ops-observability',
  'governance-matrix': 'cmd-layout--governance-matrix',
  'master-templates': 'cmd-layout--master-templates',
}
const layoutClass = computed(() => layoutClassMap[props.module.layout] || '')
const pageTestId = computed(() => {
  if (route.name === 'workshop-dashboard') return 'workshop-dashboard'
  const map = {
    '05': 'factory-dashboard',
    '06': 'review-ingestion-center-v2',
    '12': 'live-dashboard'
  }
  return map[props.module.moduleId] || ''
})
const pageCompatClass = computed(() => ({
  'live-dashboard': props.module.moduleId === '12',
  'factory-dashboard': props.module.moduleId === '05'
}))
const factoryRows = factoryBoardMock.rows

function goRoute(name) {
  router.push({ name })
}

function refreshView() {
  router.replace({ name: route.name, query: { ...route.query, refreshed: String(Date.now()) } })
}

function severityTone(value) {
  if (value === '高') return 'danger'
  if (value === '中') return 'warning'
  if (value === '低') return 'success'
  return 'neutral'
}

function qualityStatusTone(value) {
  if (value === '待处置') return 'pending'
  if (value === '处理中') return 'processing'
  if (value === '已处置') return 'success'
  if (value === '已关闭') return 'closed'
  return 'neutral'
}
const brainRisks = [
  { title: '今日摘要', value: '产量 5,824 吨' },
  { title: '风险 Top5', value: '质量波动 · 中风险' },
  { title: '建议动作', value: '复核热轧区补录' },
  { title: '可信度', value: '92%' }
]
const opsTimeline = ['10:00', '10:03', '10:12', '10:15', '10:18']
const opsServices = ['API 网关 98ms', '业务服务 210ms', '数据库 12ms', '消息队列 35ms']
const governanceRows = [
  { role: '系统管理员', entry: '✓', review: '✓', master: '✓', export: '✓' },
  { role: '生产主管', entry: '✓', review: '✓', master: '-', export: '✓' },
  { role: '班组长', entry: '✓', review: '-', master: '-', export: '-' },
  { role: '一线员工', entry: '✓', review: '-', master: '-', export: '-' }
]
const masterTiles = [
  { icon: '车', label: '车间管理', value: '18 个车间' },
  { icon: '线', label: '班组管理', value: '56 个班组' },
  { icon: '员', label: '员工授权', value: '1,256 人' },
  { icon: '机', label: '机台管理', value: '342 台' },
  { icon: '模', label: '报表模板', value: '24 个模板' },
  { icon: '字', label: '字段字典', value: '186 项' }
]
</script>
