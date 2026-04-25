<template>
  <ReferencePageFrame
    module-number="11"
    title="AI 总控中心"
    :tags="['生产摘要', '风险摘要', '智能问答']"
    data-testid="assistant-brain-center"
  >
    <template #actions>
      <el-button :loading="assistantStore.loadingCapabilities" @click="load">刷新能力</el-button>
      <el-button type="primary" :loading="assistantStore.loadingProbe" @click="probe">刷新探针</el-button>
    </template>

    <section class="stat-grid">
      <article class="stat-card">
        <div class="stat-label">今日工厂摘要</div>
        <div class="stat-value">{{ summary.todayOutput }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">风险事件</div>
        <div class="stat-value">{{ summary.riskCount }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">待审建议</div>
        <div class="stat-value">{{ summary.pendingReview }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">AI 探针</div>
        <div class="stat-value">{{ summary.probeStatus }}</div>
      </article>
    </section>

    <section class="assistant-brain__grid">
      <el-card class="panel">
        <template #header>风险事件列表</template>
        <ul class="assistant-brain__list">
          <li v-for="item in riskEvents" :key="item">{{ item }}</li>
          <li v-if="!riskEvents.length">暂无风险事件</li>
        </ul>
      </el-card>

      <el-card class="panel">
        <template #header>成本异常解读</template>
        <ul class="assistant-brain__list">
          <li v-for="item in costInsights" :key="item">{{ item }}</li>
        </ul>
      </el-card>

      <el-card class="panel">
        <template #header>质量关注点</template>
        <ul class="assistant-brain__list">
          <li v-for="item in qualityInsights" :key="item">{{ item }}</li>
        </ul>
      </el-card>

      <el-card class="panel">
        <template #header>数据接入问题</template>
        <ul class="assistant-brain__list">
          <li v-for="item in ingestionInsights" :key="item">{{ item }}</li>
        </ul>
      </el-card>

      <el-card class="panel">
        <template #header>运维健康摘要</template>
        <div class="page-stack">
          <el-alert
            v-if="assistantStore.liveProbe"
            :title="assistantStore.liveProbe.overall_ok ? '整体可用' : '存在阻塞'"
            :type="assistantStore.liveProbe.overall_ok ? 'success' : 'warning'"
            :description="probeDescription"
            show-icon
            :closable="false"
          />
          <el-alert v-else title="尚未拉取探针结果" type="info" show-icon :closable="false" />
          <div class="note">接口：`/api/v1/assistant/live-probe`</div>
        </div>
      </el-card>
    </section>

    <el-card class="panel">
      <template #header>智能问答</template>
      <div class="page-stack">
        <el-input
          v-model="query"
          type="textarea"
          :rows="3"
          placeholder="例如：今天哪个车间成本吨耗最高，原因是什么？"
        />
        <div class="header-actions">
          <el-button type="primary" :loading="assistantStore.querying" @click="ask">提问</el-button>
        </div>
        <el-alert v-if="assistantStore.lastError" :title="assistantStore.lastError" type="error" show-icon :closable="false" />
        <div v-if="assistantStore.history.length" class="page-stack">
          <article v-for="item in assistantStore.history.slice(0, 8)" :key="item.at" class="panel" style="padding: 12px;">
            <div class="stat-label">Q: {{ item.query }}</div>
            <div class="note">A: {{ item.response?.answer || item.response?.summary || '已完成' }}</div>
          </article>
        </div>
      </div>
    </el-card>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { fetchFactoryDashboard } from '../../api/dashboard'
import { useAssistantStore } from '../../stores/assistant'
import { formatNumber } from '../../utils/display'

const assistantStore = useAssistantStore()
const query = ref('')
const dashboard = ref({})

const summary = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  const riskCount = Number(exceptionLane.unreported_shift_count || 0)
    + Number(exceptionLane.returned_shift_count || 0)
    + Number(exceptionLane.mobile_exception_count || 0)
  const pendingReview = Number(exceptionLane.pending_report_publish_count || 0) + Number(exceptionLane.reconciliation_open_count || 0)
  const probeStatus = assistantStore.liveProbe
    ? (assistantStore.liveProbe.overall_ok ? '就绪' : '阻塞')
    : '未检测'
  return {
    todayOutput: `${formatNumber(dashboard.value.leader_metrics?.today_total_output)} 吨`,
    riskCount: String(riskCount),
    pendingReview: String(pendingReview),
    probeStatus
  }
})

const riskEvents = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  const items = []
  if (Number(exceptionLane.unreported_shift_count || 0) > 0) items.push(`缺报班次 ${exceptionLane.unreported_shift_count} 项，建议先补报。`)
  if (Number(exceptionLane.returned_shift_count || 0) > 0) items.push(`退回班次 ${exceptionLane.returned_shift_count} 项，建议补齐异常说明。`)
  if (Number(exceptionLane.reconciliation_open_count || 0) > 0) items.push(`差异待处理 ${exceptionLane.reconciliation_open_count} 项，建议优先处理高风险条目。`)
  return items
})

const costInsights = computed(() => [
  '优先关注单吨能耗波动与产量下降叠加场景。',
  '当成本上升且交付压力增加时，优先检查退回与缺报链路。'
])

const qualityInsights = computed(() => [
  '质量告警与退回班次应联动查看，避免重复处理。',
  '同车间连续异常建议触发升级处置。'
])

const ingestionInsights = computed(() => [
  '导入失败先按字段聚类，再回看模板映射与源文件规范。',
  '建议优先处理高频失败字段。'
])

const probeDescription = computed(() => {
  const probe = assistantStore.liveProbe
  if (!probe) return ''
  return `文本=${probe.text_probe_ok ? '正常' : '异常'} | 图像=${probe.image_probe_ok ? '正常' : '异常'}`
})

async function load() {
  await Promise.all([
    assistantStore.loadCapabilities(true),
    fetchFactoryDashboard().then((payload) => { dashboard.value = payload || {} })
  ])
}

async function probe() {
  await assistantStore.loadLiveProbe()
}

async function ask() {
  const prompt = String(query.value || '').trim()
  if (!prompt) return
  try {
    await assistantStore.ask(prompt, 'answer')
    query.value = ''
  } catch {
    // Error is handled in assistant store and interceptor.
  }
}

onMounted(async () => {
  await load()
  await probe()
})
</script>

<style scoped>
.assistant-brain__header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.assistant-brain__header h1 {
  margin: 0;
}

.assistant-brain__header p {
  margin: 6px 0 0;
  color: var(--app-muted);
}

.assistant-brain__grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.assistant-brain__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

@media (max-width: 960px) {
  .assistant-brain__header {
    flex-direction: column;
  }

  .assistant-brain__grid {
    grid-template-columns: 1fr;
  }
}
</style>
