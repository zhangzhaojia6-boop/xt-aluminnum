<template>
  <ReferencePageFrame
    module-number="16"
    title="路线图与下一步"
    :tags="['当前推进', '下一阶段', '后续排期']"
    class="review-roadmap-center"
    data-testid="review-roadmap-center"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="stat-grid" v-loading="loading">
      <article class="stat-card">
        <div class="stat-label">全链路状态</div>
        <div class="stat-value">{{ readinessLabel }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">优先级</div>
        <div class="stat-value">{{ priorityLabel }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">阻塞项</div>
        <div class="stat-value">{{ blockingCount }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">数据缺口</div>
        <div class="stat-value">{{ gapCount }}</div>
      </article>
    </section>

    <section class="review-roadmap-center__lanes" v-loading="loading">
      <el-card class="panel review-roadmap-center__lane">
        <template #header>当前推进</template>
        <ul class="review-roadmap-center__list">
          <li v-for="item in nowItems" :key="`now-${item}`">{{ item }}</li>
          <li v-if="!nowItems.length">无</li>
        </ul>
      </el-card>
      <el-card class="panel review-roadmap-center__lane">
        <template #header>下一阶段</template>
        <ul class="review-roadmap-center__list">
          <li v-for="item in nextItems" :key="`next-${item}`">{{ item }}</li>
          <li v-if="!nextItems.length">无</li>
        </ul>
      </el-card>
      <el-card class="panel review-roadmap-center__lane">
        <template #header>后续排期</template>
        <ul class="review-roadmap-center__list">
          <li v-for="item in laterItems" :key="`later-${item}`">{{ item }}</li>
          <li v-if="!laterItems.length">无</li>
        </ul>
      </el-card>
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, ref, watch } from 'vue'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { fetchFactoryDashboard } from '../../api/dashboard'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const dashboard = ref({})

const analysisHandoff = computed(() => dashboard.value.analysis_handoff || {})

const readinessLabel = computed(() => (analysisHandoff.value.readiness ? '就绪' : '待补齐'))
const priorityLabel = computed(() => analysisHandoff.value.priority || '--')
const blockingCount = computed(() => (analysisHandoff.value.blocking_reasons || []).length)
const gapCount = computed(() => (analysisHandoff.value.data_gaps || []).length)

const actionMatrix = computed(() => analysisHandoff.value.action_matrix || {})

const nowItems = computed(() => {
  const items = [
    ...(analysisHandoff.value.blocking_reasons || []),
    ...(actionMatrix.value.reporting || []),
    ...(actionMatrix.value.delivery || []),
    ...(actionMatrix.value.risk || []),
  ]
  return Array.from(new Set(items)).slice(0, 8)
})

const nextItems = computed(() => {
  const items = [
    ...(actionMatrix.value.energy || []),
    ...(actionMatrix.value.contracts || []),
    ...(analysisHandoff.value.data_gaps || []),
  ]
  return Array.from(new Set(items)).slice(0, 8)
})

const laterItems = computed(() => {
  const items = [
    '跨模块自动调度',
    '多角色审批链',
    '成本参数策略模板',
    '异常闭环自动化',
    ...(analysisHandoff.value.attention_flags || []),
  ]
  return Array.from(new Set(items)).slice(0, 8)
})

async function load() {
  loading.value = true
  try {
    dashboard.value = await fetchFactoryDashboard({ target_date: targetDate.value })
  } finally {
    loading.value = false
  }
}

watch(targetDate, load)
onMounted(load)
</script>

<style scoped>
.review-roadmap-center__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.review-roadmap-center__header h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.15;
  color: var(--app-text);
}

.review-roadmap-center__lanes {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.review-roadmap-center__lane {
  min-height: 210px;
}

.review-roadmap-center__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

@media (max-width: 1024px) {
  .review-roadmap-center__lanes {
    grid-template-columns: 1fr;
  }
}
</style>
