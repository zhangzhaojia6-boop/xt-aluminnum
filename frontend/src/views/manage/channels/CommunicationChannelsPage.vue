<template>
  <section class="xt-channels" data-testid="communication-channels-page" data-visual-pass="stitch-industrial-channel-console">
    <div class="xt-channels__backdrop" aria-hidden="true"></div>

    <header class="xt-channels__hero">
      <div>
        <span>外部通讯配置</span>
        <h1>通讯通道中心</h1>
      </div>
      <button type="button" class="xt-channels__refresh" @click="loadChannels">
        {{ loading ? '读取中' : '刷新通道' }}
      </button>
    </header>

    <div v-if="errorText" class="xt-channels__state is-error">
      <span>{{ errorText }}</span>
      <button type="button" @click="loadChannels">重新读取</button>
    </div>

    <div class="xt-channels__metrics" aria-label="通道状态">
      <article v-for="card in metricCards" :key="card.key">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.meta }}</small>
      </article>
    </div>

    <section class="xt-channels__panel">
      <header>
        <div>
          <h2>通道清单</h2>
          <span>所有外发均进入发件箱统一分发</span>
        </div>
        <b>通道状态</b>
      </header>

      <div v-if="loading" class="xt-channels__empty">读取中</div>
      <div v-else-if="channels.length === 0" class="xt-channels__empty">暂无记录</div>
      <div v-else class="xt-channels__table-wrap">
        <table>
          <thead>
            <tr>
              <th>通道名称</th>
              <th>类型</th>
              <th>范围</th>
              <th>通道标识</th>
              <th>绑定数量</th>
              <th>模式</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in channels" :key="item.id">
              <td>
                <b>{{ item.name || '未命名通道' }}</b>
                <small>{{ formatTime(item.updated_at) }}</small>
              </td>
              <td>{{ channelTypeLabel(item.channel_type) }}</td>
              <td>{{ targetLabel(item) }}</td>
              <td>{{ item.channel_key_masked || '未配置' }}</td>
              <td>{{ displayNumber(item.binding_total) }}</td>
              <td>
                <span class="xt-channels__tag" :class="{ 'is-warning': item.dry_run }">
                  {{ item.dry_run ? '演练模式' : '真实发送' }}
                </span>
              </td>
              <td>
                <span class="xt-channels__tag" :class="{ 'is-muted': !item.is_active }">
                  {{ item.is_active ? '启用' : '停用' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchCommunicationChannels } from '../../../api/agent-management.js'

const loading = ref(false)
const errorText = ref('')
const channels = ref([])
const summary = ref({})

const activeTotal = computed(() => channels.value.filter((item) => item.is_active).length)
const dryRunTotal = computed(() => channels.value.filter((item) => item.dry_run).length)
const realSendTotal = computed(() => channels.value.filter((item) => item.is_active && !item.dry_run).length)

const metricCards = computed(() => [
  { key: 'total', label: '通道总数', value: displayNumber(summary.value.channel_total ?? channels.value.length), meta: '统一治理' },
  { key: 'active', label: '启用通道', value: displayNumber(summary.value.active_channel_total ?? activeTotal.value), meta: '当前可用' },
  { key: 'dry-run', label: '演练模式', value: displayNumber(dryRunTotal.value), meta: '只写日志' },
  { key: 'real', label: '真实发送', value: displayNumber(realSendTotal.value), meta: '按后端配置执行' }
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

function channelTypeLabel(value) {
  const labels = {
    dingtalk_group: '钉钉群',
    dingtalk_work_notification: '钉钉工作通知',
    wecom_group: '企业微信群',
    internal_notice: '内部通知'
  }
  return labels[value] || '未知通道'
}

function targetLabel(item) {
  if (item?.workshop_id) return `车间 ${item.workshop_id}`
  if (item?.team_id) return `班组 ${item.team_id}`
  const labels = {
    factory: '全厂',
    workshop: '车间',
    team: '班组',
    group: '群组',
    user: '个人'
  }
  return labels[item?.target_type] || '全厂'
}

async function loadChannels() {
  loading.value = true
  errorText.value = ''
  try {
    const data = await fetchCommunicationChannels({ limit: 100 })
    channels.value = data?.channels || []
    summary.value = data?.summary || {}
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '通道读取失败'
    channels.value = []
    summary.value = {}
  } finally {
    loading.value = false
  }
}

onMounted(loadChannels)
</script>

<style scoped>
.xt-channels {
  position: relative;
  isolation: isolate;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  overflow-x: hidden;
  color: rgba(245, 247, 239, 0.94);
}

.xt-channels__backdrop {
  position: absolute;
  inset: -24px 0;
  z-index: -1;
  opacity: 0.66;
  background:
    linear-gradient(rgba(166, 124, 72, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(166, 124, 72, 0.05) 1px, transparent 1px),
    radial-gradient(circle at 18% 0, rgba(166, 124, 72, 0.18), transparent 34%),
    linear-gradient(180deg, rgba(10, 14, 18, 0.2), rgba(10, 14, 18, 0.96));
  background-size: 34px 34px, 34px 34px, 100% 100%, 100% 100%;
  pointer-events: none;
}

.xt-channels__hero,
.xt-channels__metrics article,
.xt-channels__panel,
.xt-channels__state {
  border: 1px solid rgba(166, 124, 72, 0.32);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(30, 35, 38, 0.96), rgba(13, 17, 21, 0.96)),
    #11161b;
  box-shadow: inset 1px 1px 0 rgba(255, 255, 255, 0.035);
}

.xt-channels__hero {
  min-height: 116px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-5);
}

.xt-channels__hero span {
  color: rgba(210, 166, 98, 0.9);
  font-size: var(--xt-text-sm);
  font-weight: 900;
  letter-spacing: 0.08em;
}

.xt-channels__hero h1 {
  margin: 0;
  color: rgba(245, 247, 239, 0.98);
  font-family: var(--xt-font-display);
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 900;
  letter-spacing: -0.02em;
}

.xt-channels__refresh,
.xt-channels__state button {
  border: 1px solid rgba(210, 166, 98, 0.42);
  border-radius: 8px;
  background: rgba(166, 124, 72, 0.12);
  color: rgba(255, 232, 190, 0.95);
  cursor: pointer;
  font-weight: 900;
}

.xt-channels__refresh {
  min-height: 36px;
  padding: 0 var(--xt-space-4);
}

.xt-channels__state {
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--xt-space-3);
  color: rgba(255, 192, 174, 0.96);
  font-weight: 900;
}

.xt-channels__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-channels__metrics article {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 118px;
  padding: var(--xt-space-4);
}

.xt-channels__metrics span,
.xt-channels__panel header span {
  color: rgba(210, 166, 98, 0.75);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.06em;
}

.xt-channels__metrics strong {
  color: rgba(245, 247, 239, 0.98);
  font-family: var(--xt-font-mono);
  font-size: clamp(28px, 3vw, 42px);
  line-height: 1;
}

.xt-channels__metrics small {
  color: rgba(193, 207, 202, 0.72);
  font-weight: 850;
}

.xt-channels__panel {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  overflow: hidden;
}

.xt-channels__panel header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding-bottom: var(--xt-space-3);
  border-bottom: 1px solid rgba(166, 124, 72, 0.18);
}

.xt-channels__panel h2 {
  margin: 0;
  color: rgba(245, 247, 239, 0.96);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-channels__panel header b {
  color: rgba(210, 166, 98, 0.9);
  font-size: var(--xt-text-sm);
}

.xt-channels__empty {
  min-height: 104px;
  display: grid;
  place-items: center;
  border: 1px dashed rgba(166, 124, 72, 0.28);
  border-radius: 10px;
  color: rgba(193, 207, 202, 0.68);
  font-weight: 900;
}

.xt-channels__table-wrap {
  overflow-x: auto;
}

.xt-channels table {
  width: 100%;
  min-width: 820px;
  border-collapse: collapse;
}

.xt-channels th,
.xt-channels td {
  padding: 12px var(--xt-space-2);
  border-bottom: 1px solid rgba(166, 124, 72, 0.1);
  text-align: left;
  vertical-align: middle;
}

.xt-channels th {
  color: rgba(210, 166, 98, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-channels td {
  color: rgba(245, 247, 239, 0.84);
  font-size: var(--xt-text-sm);
}

.xt-channels td b,
.xt-channels td small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-channels td b {
  color: rgba(245, 247, 239, 0.95);
  font-weight: 900;
}

.xt-channels td small {
  color: rgba(193, 207, 202, 0.62);
  font-size: var(--xt-text-xs);
  font-weight: 760;
}

.xt-channels__tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px var(--xt-space-2);
  border: 1px solid rgba(57, 217, 138, 0.3);
  border-radius: 4px;
  background: rgba(57, 217, 138, 0.1);
  color: rgba(137, 255, 205, 0.94);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-channels__tag.is-warning {
  border-color: rgba(210, 166, 98, 0.36);
  background: rgba(166, 124, 72, 0.13);
  color: rgba(255, 232, 190, 0.94);
}

.xt-channels__tag.is-muted {
  border-color: rgba(132, 148, 149, 0.24);
  background: rgba(49, 53, 60, 0.28);
  color: rgba(185, 202, 203, 0.74);
}

@media (max-width: 900px) {
  .xt-channels__hero,
  .xt-channels__panel header {
    align-items: flex-start;
    flex-direction: column;
  }

  .xt-channels__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .xt-channels__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
