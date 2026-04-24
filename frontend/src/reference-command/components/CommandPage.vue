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
      <img class="cmd-factory-board__visual" :src="factoryBoardImage" alt="" />
      <div class="cmd-factory-board__functional">
      <div class="cmd-factory-board__top">
        <span class="cmd-factory-board__lead">车间 / 产线日内作业</span>
        <div class="review-home-hero__controls cmd-factory-board__date">
          <label class="el-date-editor">
            <input v-model="targetDate" aria-label="目标日期" />
          </label>
        </div>
        <div class="cmd-factory-board__badges">
          <span class="cmd-status" data-testid="delivery-ready-card">日报交付就绪</span>
          <button type="button" role="tab" class="cmd-button">关注</button>
          <span class="cmd-status" data-testid="delivery-missing-steps">待补齐步骤</span>
        </div>
      </div>

      <div data-testid="review-command-deck" class="cmd-factory-board__main">
        <table class="cmd-table cmd-factory-table">
          <thead>
            <tr>
              <th>车间/产线</th>
              <th>产量（吨）</th>
              <th>OEE</th>
              <th>良率/成品率</th>
              <th>异常</th>
              <th>趋势（24h）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in factoryRows" :key="row.name">
              <td>{{ row.name }}</td>
              <td>{{ row.output }}</td>
              <td>{{ row.oee }}</td>
              <td>{{ row.quality }}</td>
              <td :class="{ 'is-risk': row.risk !== '0' }">{{ row.risk }}</td>
              <td><CommandTrend :values="row.trend" /></td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>合计/平均</td>
              <td>5,824</td>
              <td>92.3%</td>
              <td>96.2%</td>
              <td class="is-risk">4</td>
              <td><CommandTrend :values="[8, 12, 10, 15, 13, 16, 14]" /></td>
            </tr>
          </tfoot>
        </table>

        <aside class="cmd-factory-board__side">
          <div class="cmd-factory-metrics" aria-label="工厂汇总指标">
            <article v-for="card in factoryCards" :key="card.label" class="stat-card">
              <span>{{ card.label }}</span>
              <strong class="stat-value">{{ card.value }}</strong>
              <em>{{ card.trend }}</em>
            </article>
          </div>
          <div data-testid="agent-runtime-flow" class="cmd-factory-ai">
            <strong>算法流水线</strong>
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
      </div>
    </section>

    <template v-else>
      <div v-if="module.moduleId === '13'" data-testid="review-governance-center" class="cmd-status">权限治理在线</div>
      <div v-if="module.moduleId === '13'" data-testid="admin-users-center" class="cmd-status">用户治理在线</div>
      <div v-if="module.moduleId === '14'" data-testid="admin-home" class="cmd-status">管理总览在线</div>
      <div v-if="module.moduleId === '14'" data-testid="admin-master-center" class="cmd-status">主数据在线</div>
      <div v-if="module.moduleId === '14'" data-testid="template-editor-page" class="cmd-status">模板中心在线</div>

      <section :class="['cmd-target-layout', layoutClass]">
        <template v-if="module.moduleId === '06'">
          <div class="cmd-module-page__primary">
            <div class="cmd-source-list">
              <span v-for="source in mappingSources" :key="source.name">
                <i></i>{{ source.name }}<strong>{{ source.state }}</strong>
              </span>
            </div>
            <table class="cmd-table">
              <thead><tr><th>源字段</th><th>目标字段</th><th>类型</th><th>映射状态</th></tr></thead>
              <tbody>
                <tr v-for="row in mappingFields" :key="row.source">
                  <td>{{ row.source }}</td><td>{{ row.target }}</td><td>{{ row.type }}</td><td>{{ row.state }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <aside class="cmd-module-page__side cmd-ring-card">
            <strong>导入成功率</strong>
            <div class="cmd-ring">96%</div>
            <span>今日 5 个文件 · 12 项映射</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '07'">
          <table class="cmd-table cmd-module-page__primary">
            <thead><tr><th>消息源</th><th>班次</th><th>提交时间</th><th>异常类型</th><th>AI 建议</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="row in reviewQueue" :key="row.time">
                <td>{{ row.source }}</td><td>{{ row.shift }}</td><td>{{ row.time }}</td><td>{{ row.type }}</td><td>{{ row.ai }}</td>
                <td><button type="button" class="cmd-mini-button">通过</button></td>
              </tr>
            </tbody>
          </table>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>批量操作</strong>
            <button type="button" class="cmd-button is-primary">批量通过</button>
            <button type="button" class="cmd-button">批量驳回</button>
            <CommandTrend :values="viewModel.trend" />
          </aside>
        </template>

        <template v-else-if="module.moduleId === '08'">
          <div class="cmd-module-page__primary cmd-report-grid">
            <CommandKpi v-for="kpi in viewModel.kpis" :key="kpi.label" v-bind="kpi" />
            <CommandTrend class="cmd-wide-trend" :values="[20, 24, 22, 32, 29, 35, 38, 34]" />
          </div>
          <aside class="cmd-module-page__side cmd-delivery-list">
            <strong>交付清单</strong>
            <span>计划交付 <b>23 车</b></span>
            <span>已交付 <b>20 车</b></span>
            <span>待交付 <b>3 车</b></span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '09'">
          <table class="cmd-table cmd-module-page__primary">
            <thead><tr><th>时间</th><th>来源</th><th>类型</th><th>严重度</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="row in qualityAlerts" :key="row.time">
                <td>{{ row.time }}</td><td>{{ row.source }}</td><td>{{ row.type }}</td><td>{{ row.level }}</td><td>{{ row.state }}</td>
              </tr>
            </tbody>
          </table>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>质量处置建议</strong>
            <span>AI 分类与诊断</span><span>建议快速复检</span><span>执行与追踪</span><span>关闭历史批次</span>
          </aside>
        </template>

        <template v-else-if="module.moduleId === '10'">
          <div class="cmd-module-page__primary cmd-cost-bars">
            <div v-for="row in costRows" :key="row.name" class="cmd-cost-row">
              <span>{{ row.name }}</span>
              <i :style="{ '--cmd-bar': row.value }"></i>
              <strong>{{ row.amount }}</strong>
            </div>
          </div>
          <aside class="cmd-module-page__side cmd-stack-list">
            <strong>调节方案</strong>
            <span>吨铝成本拆分</span><span>电耗偏高回收</span><span>人工排班优化</span>
            <button type="button" class="cmd-button is-primary">调节方案</button>
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

        <template v-else-if="module.moduleId === '16'">
          <div class="cmd-module-page__primary cmd-roadmap">
            <article v-for="phase in roadmapPhases" :key="phase.title">
              <strong>{{ phase.title }}</strong>
              <span v-for="item in phase.items" :key="item">{{ item }}</span>
              <em>{{ phase.progress }}</em>
            </article>
          </div>
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
import { useRoute } from 'vue-router'

import CommandActionBar from './CommandActionBar.vue'
import CommandFlowMap from './CommandFlowMap.vue'
import CommandKpi from './CommandKpi.vue'
import CommandStatus from './CommandStatus.vue'
import CommandTable from './CommandTable.vue'
import CommandTrend from './CommandTrend.vue'
import factoryBoardImage from '../assets/factory-board.png'

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
const assistantOpen = ref(false)
const targetDate = ref(new Date().toISOString().slice(0, 10))

const statusLabel = computed(() => props.viewModel.statuses?.[0]?.label || '在线')
const showFactoryCompat = computed(() => props.module.moduleId === '05' && route.name !== 'workshop-dashboard')
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
  roadmap: 'cmd-layout--roadmap'
}
const layoutClass = computed(() => layoutClassMap[props.module.layout] || '')
const pageTestId = computed(() => {
  if (route.name === 'workshop-dashboard') return 'workshop-dashboard'
  const map = {
    '05': 'factory-dashboard',
    '06': 'review-ingestion-center-v2',
    '12': 'live-dashboard',
    '16': 'review-roadmap-center'
  }
  return map[props.module.moduleId] || ''
})
const pageCompatClass = computed(() => ({
  'live-dashboard': props.module.moduleId === '12',
  'factory-dashboard': props.module.moduleId === '05'
}))
const factoryCards = [
  { label: '合同量', value: '8,560', trend: '+2.1%' },
  { label: '今日发货', value: '5,824', trend: '+8.6%' },
  { label: '今日产量', value: '5,824', trend: '+8.6%' }
]
const factoryRows = [
  { name: '铸造一线', output: '1,265', oee: '92.1%', quality: '96.3%', risk: '1', trend: [12, 18, 15, 22, 19, 28, 24] },
  { name: '铸造二线', output: '1,132', oee: '94.6%', quality: '97.1%', risk: '0', trend: [10, 12, 16, 14, 18, 20, 23] },
  { name: '精整区', output: '986', oee: '91.3%', quality: '95.6%', risk: '2', trend: [9, 11, 10, 15, 13, 18, 16] },
  { name: '热轧区', output: '1,432', oee: '90.4%', quality: '94.2%', risk: '1', trend: [18, 15, 19, 22, 20, 24, 27] },
  { name: '拉矫区', output: '1,009', oee: '93.0%', quality: '96.0%', risk: '0', trend: [8, 12, 11, 14, 18, 17, 19] }
]
const mappingSources = [
  { name: 'MES', state: '已接入' },
  { name: 'PLC', state: '已接入' },
  { name: '质检系统', state: '已接入' },
  { name: 'ERP', state: '已接入' },
  { name: '手工导入', state: '待办' }
]
const mappingFields = [
  { source: 'order_id', target: '订单编号', type: 'String', state: '已映射' },
  { source: 'product_code', target: '产品编码', type: 'String', state: '已映射' },
  { source: 'actual_weight', target: '实际重量', type: 'Float', state: '已映射' },
  { source: 'bad_qty', target: '不良数量', type: 'Integer', state: '已映射' },
  { source: 'create_time', target: '生产时间', type: 'DateTime', state: '已映射' }
]
const reviewQueue = [
  { source: '铸造一线', shift: '白班', time: '05-21 10:10', type: '成品率偏低', ai: '建议复核' },
  { source: '精整区', shift: '白班', time: '05-21 10:05', type: '能耗异常', ai: '中风险' },
  { source: '热轧区', shift: '夜班', time: '05-21 09:50', type: '产量异常', ai: '建议补录' },
  { source: '铸造二线', shift: '白班', time: '05-21 09:45', type: '质量波动', ai: '中风险' }
]
const qualityAlerts = [
  { time: '10:12', source: '铸造一线', type: '成品率', level: '高', state: '处理中' },
  { time: '09:58', source: '热轧区', type: '长宽偏差', level: '中', state: '待确认' },
  { time: '09:40', source: '精整区', type: '复检异常', level: '中', state: '待确认' },
  { time: '08:50', source: '拉矫区', type: '设备停机', level: '低', state: '已闭环' }
]
const costRows = [
  { name: '人工', value: '36%', amount: '1,245' },
  { name: '电耗', value: '52%', amount: '632' },
  { name: '天然气', value: '28%', amount: '324' },
  { name: '公辅分摊', value: '42%', amount: '186' },
  { name: '其他', value: '22%', amount: '98' }
]
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
const roadmapPhases = [
  { title: '当前阶段', progress: '进行中 80%', items: ['核心流程上线', '班组入口稳定', '权限与日报闭环'] },
  { title: '中期', progress: '进行中 45%', items: ['成本模型优化', '集团 KPI 看板', 'AI 质量诊断'] },
  { title: '长期', progress: '规划中 15%', items: ['跨厂协同', '供应商联动', '智能排产'] }
]
</script>
