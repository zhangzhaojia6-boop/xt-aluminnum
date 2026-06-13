<template>
  <section class="xt-agent-management" data-testid="agent-management-page" data-visual-pass="stitch-industrial-blue-governance">
    <div class="xt-agent-management__backdrop" aria-hidden="true"></div>

    <header class="xt-agent-management__hero">
      <div>
        <span>多智能体外部通讯</span>
        <h1>通讯治理台</h1>
      </div>
      <div class="xt-agent-management__status">
        <i :class="{ 'is-warning': hasPendingWork }"></i>
        <span>{{ runtimeLabel }}</span>
      </div>
    </header>

    <div v-if="loading" class="xt-agent-management__state is-loading">读取中</div>
    <div v-else-if="errorText" class="xt-agent-management__state is-error">
      <span>读取失败</span>
      <button type="button" @click="loadOverview">重新读取</button>
    </div>

    <div class="xt-agent-management__metrics" aria-label="通讯治理指标">
      <article v-for="card in metricCards" :key="card.key" class="xt-agent-management__metric" :class="`is-${card.tone}`">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.meta }}</small>
      </article>
    </div>

    <div class="xt-agent-management__grid">
      <section class="xt-agent-management__panel is-wide">
        <header>
          <h2>智能体状态</h2>
          <span>{{ agents.length }} 个</span>
        </header>
        <div v-if="agents.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>类型</th>
                <th>范围</th>
                <th>绑定</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in agents" :key="item.id">
                <td>
                  <b>{{ item.name }}</b>
                  <small>{{ item.code }}</small>
                </td>
                <td>{{ item.agent_type || '未配置' }}</td>
                <td>{{ item.scope_type || '全厂' }}</td>
                <td>{{ item.binding_total || 0 }}</td>
                <td><span class="xt-agent-management__tag" :class="{ 'is-muted': !item.is_active }">{{ item.is_active ? '运行' : '停用' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="xt-agent-management__panel">
        <header>
          <h2>通道治理</h2>
          <span>{{ channels.length }} 条</span>
        </header>
        <div v-if="channels.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__list">
          <article v-for="item in channels" :key="item.id" class="xt-agent-management__row">
            <div>
              <b>{{ item.name }}</b>
              <small>{{ item.channel_type }} / {{ item.channel_key_masked }}</small>
            </div>
            <span class="xt-agent-management__tag" :class="{ 'is-warning': item.dry_run, 'is-muted': !item.is_active }">
              {{ channelState(item) }}
            </span>
          </article>
        </div>
      </section>

      <section class="xt-agent-management__panel is-wide">
        <header>
          <h2>多模态证据</h2>
          <span>{{ evidence.length }} 条</span>
        </header>
        <div v-if="evidence.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__evidence">
          <article v-for="item in evidence" :key="item.id">
            <span>{{ evidenceTypeLabel(item.evidence_type) }}</span>
            <b>{{ item.recognized_text || '待识别' }}</b>
            <small>{{ item.confirmation_status || '待确认' }}</small>
          </article>
        </div>
      </section>

      <section class="xt-agent-management__panel">
        <header>
          <h2>最近事件</h2>
          <span>{{ events.length }} 条</span>
        </header>
        <div v-if="events.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <ol v-else class="xt-agent-management__timeline">
          <li v-for="item in events" :key="item.id">
            <i :class="`is-${item.severity || 'info'}`"></i>
            <div>
              <b>{{ eventTypeLabel(item.event_type) }}</b>
              <small>{{ item.summary || item.source_ref || '无补充信息' }}</small>
              <time>{{ formatTime(item.occurred_at || item.created_at) }}</time>
            </div>
          </li>
        </ol>
      </section>

      <section class="xt-agent-management__panel">
        <header>
          <h2>待审核操作</h2>
          <span>{{ operationApprovals.length }} 条</span>
        </header>
        <div v-if="operationApprovals.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__list">
          <article v-for="item in operationApprovals" :key="item.id" class="xt-agent-management__row">
            <div>
              <b>{{ operationTypeLabel(item.operation_type) }}</b>
              <small>{{ item.trace_id || '无追踪号' }} / {{ executionStateLabel(item) }}</small>
            </div>
            <span class="xt-agent-management__tag is-warning">{{ approvalStateLabel(item.status) }}</span>
          </article>
        </div>
      </section>

      <section class="xt-agent-management__panel">
        <header>
          <h2>发件箱</h2>
          <span>{{ outbox.length }} 条</span>
        </header>
        <div v-if="outbox.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__list">
          <article v-for="item in outbox" :key="item.id" class="xt-agent-management__row">
            <div>
              <b>{{ item.title }}</b>
              <small>{{ item.trace_id }} / 尝试 {{ item.attempts || 0 }} 次</small>
            </div>
            <span class="xt-agent-management__tag" :class="{ 'is-warning': item.status === 'pending', 'is-muted': item.status === 'dry_run' }">
              {{ outboxStateLabel(item.status) }}
            </span>
          </article>
        </div>
      </section>

      <section class="xt-agent-management__panel">
        <header>
          <h2>知识口径</h2>
          <span>{{ knowledgeEntries.length }} 条</span>
        </header>
        <div v-if="knowledgeEntries.length === 0" class="xt-agent-management__empty">暂无记录</div>
        <div v-else class="xt-agent-management__list">
          <article v-for="item in knowledgeEntries" :key="item.entry_id" class="xt-agent-management__row">
            <div>
              <b>{{ item.title }}</b>
              <small>{{ knowledgeCategoryLabel(item.category) }} / {{ item.source_ref || '无来源' }}</small>
            </div>
            <span class="xt-agent-management__tag">{{ (item.tags || []).length }} 项</span>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchAgentManagementOverview } from '../../../api/agent-management.js'

const EMPTY_OVERVIEW = {
  safe_mode: true,
  summary: {},
  agents: [],
  channels: [],
  events: [],
  evidence: [],
  operation_approvals: [],
  outbox: [],
  knowledge_entries: []
}

const loading = ref(false)
const errorText = ref('')
const overview = ref({ ...EMPTY_OVERVIEW })

const summary = computed(() => overview.value?.summary || {})
const agents = computed(() => overview.value?.agents || [])
const channels = computed(() => overview.value?.channels || [])
const events = computed(() => overview.value?.events || [])
const evidence = computed(() => overview.value?.evidence || [])
const operationApprovals = computed(() => overview.value?.operation_approvals || [])
const outbox = computed(() => overview.value?.outbox || [])
const knowledgeEntries = computed(() => overview.value?.knowledge_entries || [])
const hasPendingWork = computed(() => Number(summary.value.pending_event_total || 0) > 0 || Number(summary.value.pending_operation_total || 0) > 0)
const runtimeLabel = computed(() => (loading.value ? '读取中' : hasPendingWork.value ? '有待处理项' : '安全运行'))

const metricCards = computed(() => [
  { key: 'agent', label: '智能体总数', value: displayNumber(summary.value.agent_total), meta: `运行 ${displayNumber(summary.value.active_agent_total)}`, tone: 'cyan' },
  { key: 'channel', label: '活跃通道', value: displayNumber(summary.value.active_channel_total), meta: `总通道 ${displayNumber(summary.value.channel_total)}`, tone: 'blue' },
  { key: 'event', label: '待处理事件', value: displayNumber(summary.value.pending_event_total), meta: '异常与主动汇报', tone: hasPendingWork.value ? 'warning' : 'cyan' },
  { key: 'evidence', label: '证据确权', value: displayNumber(summary.value.evidence_total), meta: `审批 ${displayNumber(summary.value.pending_operation_total)}`, tone: 'green' },
  { key: 'knowledge', label: '知识口径', value: displayNumber(summary.value.knowledge_entry_total), meta: '资料来源可追溯', tone: 'blue' }
])

function displayNumber(value) {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

function formatTime(value) {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function channelState(item) {
  if (!item?.is_active) return '停用'
  return item.dry_run ? '演练' : '启用'
}

function eventTypeLabel(value) {
  const labels = {
    factory_overview: '全厂总览',
    workshop_status: '车间状态',
    anomaly_detected: '异常检测',
    machine_photo_received: '现场证据'
  }
  return labels[value] || value || '事件'
}

function evidenceTypeLabel(value) {
  const labels = {
    image: '图片',
    voice: '语音',
    attachment: '附件',
    text: '文本'
  }
  return labels[value] || value || '证据'
}

function knowledgeCategoryLabel(value) {
  const labels = {
    metric_rule: '指标口径',
    data_source_rule: '数据来源',
    time_rule: '时间口径',
    daily_report_rule: '日报规则',
    mes_field_rule: 'MES字段',
    workshop_rule: '车间规则',
    anomaly_rule: '异常处理',
    fill_rule: '填报补录',
    evidence_rule: '证据规则',
    approval_rule: '审批规则',
    permission_rule: '权限规则'
  }
  return labels[value] || value || '口径'
}

function operationTypeLabel(value) {
  const labels = {
    supplement_production: '补产量预览',
    publish_daily_report: '发布日报预览'
  }
  return labels[value] || value || '操作'
}

function approvalStateLabel(value) {
  const labels = {
    pending: '待处理',
    pending_confirmation: '待确认',
    confirmed: '已确认',
    dry_run_executed: '演练完成',
    executed: '已执行'
  }
  return labels[value] || value || '待处理'
}

function executionStateLabel(item) {
  if (item?.actual_write) return '真实执行'
  if (item?.execution_status === 'dry_run_executed' || item?.status === 'dry_run_executed') return '演练完成'
  if (item?.execution_status === 'confirmed_waiting_execution') return '等待执行'
  return '未执行'
}

function outboxStateLabel(value) {
  const labels = {
    pending: '待发送',
    retrying: '重试中',
    dry_run: '演练',
    sent: '已发送',
    failed: '失败'
  }
  return labels[value] || value || '未知'
}

async function loadOverview() {
  loading.value = true
  errorText.value = ''
  try {
    overview.value = await fetchAgentManagementOverview({ limit: 20 })
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '读取失败'
    overview.value = { ...EMPTY_OVERVIEW }
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.xt-agent-management {
  --xt-agent-bg: #0b1222;
  --xt-agent-panel: #161e31;
  --xt-agent-panel-soft: #1a2337;
  --xt-agent-border: rgba(94, 112, 143, 0.34);
  --xt-agent-blue: #1488ff;
  --xt-agent-cyan: #22d3ee;
  position: relative;
  isolation: isolate;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  overflow-x: hidden;
  color: rgba(225, 253, 255, 0.94);
}

.xt-agent-management__backdrop {
  position: absolute;
  inset: -24px 0;
  z-index: -1;
  opacity: 0.58;
  background:
    linear-gradient(rgba(20, 136, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20, 136, 255, 0.045) 1px, transparent 1px),
    linear-gradient(180deg, rgba(11, 18, 34, 0.4), rgba(11, 18, 34, 0.92));
  background-size: 32px 32px, 32px 32px, 100% 100%;
  pointer-events: none;
}

.xt-agent-management__hero,
.xt-agent-management__metric,
.xt-agent-management__panel,
.xt-agent-management__state {
  border: 1px solid var(--xt-agent-border);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(22, 30, 49, 0.96), rgba(13, 24, 43, 0.96)),
    var(--xt-agent-panel);
  box-shadow: inset 1px 1px 0 rgba(255, 255, 255, 0.035);
}

.xt-agent-management__hero {
  min-height: 118px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-5);
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(20, 136, 255, 0.16), rgba(22, 30, 49, 0.96) 52%, rgba(11, 18, 34, 0.98)),
    var(--xt-agent-panel);
}

.xt-agent-management__hero span {
  color: rgba(116, 245, 255, 0.84);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.xt-agent-management__hero h1 {
  margin: 0;
  color: rgba(225, 253, 255, 0.98);
  font-family: var(--xt-font-display);
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 900;
  letter-spacing: -0.02em;
}

.xt-agent-management__status {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid rgba(57, 217, 138, 0.32);
  border-radius: 999px;
  background: rgba(57, 217, 138, 0.1);
  color: rgba(137, 255, 205, 0.94);
  font-weight: 900;
}

.xt-agent-management__status i,
.xt-agent-management__timeline i {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: rgba(57, 217, 138, 0.95);
  box-shadow: 0 0 10px rgba(57, 217, 138, 0.45);
}

.xt-agent-management__status i.is-warning,
.xt-agent-management__timeline i.is-warning {
  background: rgba(255, 171, 0, 0.96);
  box-shadow: 0 0 10px rgba(255, 176, 32, 0.4);
}

.xt-agent-management__timeline i.is-error {
  background: rgba(255, 92, 92, 0.96);
  box-shadow: 0 0 10px rgba(255, 92, 92, 0.4);
}

.xt-agent-management__state {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--xt-space-3);
  color: rgba(185, 223, 235, 0.82);
  font-weight: 900;
}

.xt-agent-management__state.is-loading {
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.05), rgba(0, 242, 255, 0.14), rgba(0, 242, 255, 0.05)),
    rgba(4, 18, 32, 0.66);
  background-size: 240% 100%;
  animation: xt-agent-management-loading 1.2s linear infinite;
}

.xt-agent-management__state.is-error {
  border-color: rgba(255, 92, 92, 0.28);
  color: rgba(255, 168, 168, 0.94);
}

.xt-agent-management__state button {
  border: 1px solid rgba(255, 168, 168, 0.34);
  border-radius: 8px;
  background: rgba(255, 92, 92, 0.08);
  color: rgba(255, 218, 214, 0.96);
  cursor: pointer;
}

.xt-agent-management__metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-agent-management__metric {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 128px;
  padding: var(--xt-space-4);
}

.xt-agent-management__metric span,
.xt-agent-management__panel header span {
  color: rgba(185, 223, 235, 0.72);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.06em;
}

.xt-agent-management__metric strong {
  color: rgba(225, 253, 255, 0.98);
  font-family: var(--xt-font-mono);
  font-size: clamp(28px, 3vw, 42px);
  line-height: 1;
}

.xt-agent-management__metric small {
  color: rgba(34, 211, 238, 0.84);
  font-weight: 850;
}

.xt-agent-management__metric.is-warning small,
.xt-agent-management__metric.is-warning strong {
  color: rgba(255, 214, 128, 0.96);
}

.xt-agent-management__metric.is-green small {
  color: rgba(137, 255, 205, 0.9);
}

.xt-agent-management__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: var(--xt-space-4);
}

.xt-agent-management__panel {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  overflow: hidden;
}

.xt-agent-management__panel.is-wide {
  min-height: 292px;
}

.xt-agent-management__panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding-bottom: var(--xt-space-3);
  border-bottom: 1px solid rgba(0, 242, 255, 0.14);
}

.xt-agent-management__panel h2 {
  margin: 0;
  color: rgba(225, 253, 255, 0.94);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.xt-agent-management__empty {
  min-height: 98px;
  display: grid;
  place-items: center;
  border: 1px dashed rgba(0, 242, 255, 0.2);
  border-radius: 10px;
  color: rgba(185, 223, 235, 0.62);
  font-weight: 850;
}

.xt-agent-management__table-wrap {
  overflow-x: auto;
}

.xt-agent-management__table-wrap table {
  width: 100%;
  border-collapse: collapse;
  min-width: 620px;
}

.xt-agent-management__table-wrap th,
.xt-agent-management__table-wrap td {
  padding: 10px var(--xt-space-2);
  border-bottom: 1px solid rgba(0, 242, 255, 0.08);
  text-align: left;
  vertical-align: middle;
}

.xt-agent-management__table-wrap th {
  color: rgba(116, 245, 255, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-agent-management__table-wrap td {
  color: rgba(225, 253, 255, 0.82);
  font-size: var(--xt-text-sm);
}

.xt-agent-management__table-wrap td b,
.xt-agent-management__row b,
.xt-agent-management__evidence b,
.xt-agent-management__timeline b {
  display: block;
  overflow: hidden;
  color: rgba(225, 253, 255, 0.94);
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-agent-management__table-wrap td small,
.xt-agent-management__row small,
.xt-agent-management__evidence small,
.xt-agent-management__timeline small,
.xt-agent-management__timeline time {
  display: block;
  overflow: hidden;
  color: rgba(185, 223, 235, 0.62);
  font-size: var(--xt-text-xs);
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-agent-management__list,
.xt-agent-management__timeline {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  padding: 0;
}

.xt-agent-management__row,
.xt-agent-management__timeline li,
.xt-agent-management__evidence article {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
      border: 1px solid rgba(94, 112, 143, 0.22);
      border-radius: 8px;
      background: rgba(26, 35, 55, 0.62);
}

.xt-agent-management__row > div,
.xt-agent-management__timeline div {
  min-width: 0;
}

.xt-agent-management__tag {
  flex: 0 0 auto;
  padding: 3px var(--xt-space-2);
  border: 1px solid rgba(57, 217, 138, 0.3);
  border-radius: 4px;
  background: rgba(57, 217, 138, 0.1);
  color: rgba(137, 255, 205, 0.94);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-agent-management__tag.is-warning {
  border-color: rgba(255, 176, 32, 0.32);
  background: rgba(255, 176, 32, 0.1);
  color: rgba(255, 214, 128, 0.94);
}

.xt-agent-management__tag.is-muted {
  border-color: rgba(132, 148, 149, 0.26);
  background: rgba(49, 53, 60, 0.28);
  color: rgba(185, 202, 203, 0.74);
}

.xt-agent-management__evidence {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-agent-management__evidence article {
  align-items: flex-start;
  flex-direction: column;
}

.xt-agent-management__evidence article > span {
  width: fit-content;
  padding: 3px var(--xt-space-2);
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: 7px;
  color: rgba(116, 245, 255, 0.88);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-agent-management__timeline {
  list-style: none;
}

.xt-agent-management__timeline li {
  align-items: flex-start;
  justify-content: flex-start;
}

@keyframes xt-agent-management-loading {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}

@media (max-width: 1180px) {
  .xt-agent-management__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-agent-management__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .xt-agent-management {
    min-height: 0;
  }

  .xt-agent-management__hero {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--xt-space-4);
  }

  .xt-agent-management__metrics,
  .xt-agent-management__evidence {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-agent-management__state.is-loading {
    animation: none;
  }
}
</style>
