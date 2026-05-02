<template>
  <section class="ai-briefing-inbox" data-testid="ai-briefing-inbox">
    <header class="ai-briefing-inbox__head">
      <strong>主动汇报</strong>
      <el-button text :icon="Refresh" :loading="generating" @click="handleGenerate">生成</el-button>
    </header>

    <div class="ai-briefing-inbox__filters" aria-label="主动汇报状态">
      <button
        v-for="filter in stateFilters"
        :key="filter.value"
        type="button"
        :class="{ 'is-active': activeFilter === filter.value }"
        @click="activeFilter = filter.value"
      >
        {{ filter.label }}
      </button>
    </div>

    <div v-if="store.loadingBriefings && !visibleBriefings.length" class="ai-briefing-inbox__state">加载中</div>
    <div v-else-if="visibleBriefings.length" class="ai-briefing-inbox__list">
      <article
        v-for="briefing in visibleBriefings"
        :key="briefing.id"
        class="ai-briefing-inbox__item"
        :class="stateClass(briefing)"
      >
        <div class="ai-briefing-inbox__item-head">
          <span>{{ stateLabel(briefing) }}</span>
          <em>{{ briefing.severity }}</em>
        </div>
        <strong>{{ briefing.title || briefing.type || '主动汇报' }}</strong>
        <div class="ai-briefing-inbox__meta">
          <span>证据 {{ briefing.evidenceCount }}</span>
          <span>{{ briefing.scopeKey || 'factory:all' }}</span>
        </div>
        <div class="ai-briefing-inbox__actions">
          <el-button size="small" :disabled="briefing.read" @click="handleRead(briefing)">已读</el-button>
          <el-button size="small" type="primary" plain @click="handleFollowUp(briefing)">跟进</el-button>
          <el-button size="small" text @click="handleIgnore(briefing)">忽略</el-button>
        </div>
      </article>
    </div>
    <div v-else class="ai-briefing-inbox__state">暂无主动汇报</div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { useAssistantStore } from '../../stores/assistant'

const store = useAssistantStore()
const activeFilter = ref('all')
const generating = ref(false)
const ignoredIds = ref(new Set())
const stateFilters = [
  { value: 'all', label: '全部' },
  { value: 'unread', label: '未读' },
  { value: 'read', label: '已读' },
  { value: 'followed', label: '已跟进' },
  { value: 'ignored', label: '已忽略' }
]

const visibleBriefings = computed(() => {
  if (activeFilter.value === 'all') return store.briefings
  return store.briefings.filter((briefing) => briefingState(briefing) === activeFilter.value)
})

onMounted(async () => {
  try {
    await store.loadBriefings()
  } catch {
    ElMessage.error(store.lastError || '加载主动汇报失败')
  }
})

function briefingState(briefing) {
  if (ignoredIds.value.has(briefing.id) || briefing.deliverySuppressed || briefing.followUpStatus === 'ignored') return 'ignored'
  if (briefing.followUpStatus === 'followed') return 'followed'
  if (briefing.read) return 'read'
  return 'unread'
}

function stateClass(briefing) {
  return `is-${briefingState(briefing)}`
}

function stateLabel(briefing) {
  const state = briefingState(briefing)
  if (state === 'followed') return '已跟进'
  if (state === 'ignored') return '已忽略'
  if (state === 'read') return '已读'
  return '未读'
}

async function handleGenerate() {
  generating.value = true
  try {
    await store.generateBriefing()
  } catch {
    ElMessage.error(store.lastError || '生成主动汇报失败')
  } finally {
    generating.value = false
  }
}

async function handleRead(briefing) {
  if (!briefing.id || briefing.read) return
  try {
    await store.markBriefingRead(briefing.id)
  } catch {
    ElMessage.error(store.lastError || '标记已读失败')
  }
}

async function handleFollowUp(briefing) {
  if (!briefing.id) return
  try {
    await store.followUpBriefing(briefing.id)
  } catch {
    ElMessage.error(store.lastError || '标记跟进失败')
  }
}

function handleIgnore(briefing) {
  if (!briefing.id) return
  const next = new Set(ignoredIds.value)
  next.add(briefing.id)
  ignoredIds.value = next
}
</script>

<style scoped>
.ai-briefing-inbox,
.ai-briefing-inbox__list {
  display: grid;
  gap: 10px;
}

.ai-briefing-inbox__head,
.ai-briefing-inbox__item-head,
.ai-briefing-inbox__meta,
.ai-briefing-inbox__actions {
  display: flex;
  align-items: center;
}

.ai-briefing-inbox__head {
  justify-content: space-between;
}

.ai-briefing-inbox__head strong {
  color: var(--xt-text);
  font-size: 15px;
}

.ai-briefing-inbox__filters {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}

.ai-briefing-inbox__filters button {
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.ai-briefing-inbox__filters button:active {
  transform: scale(0.96);
}

.ai-briefing-inbox__filters button.is-active {
  background: var(--xt-primary);
  color: #fff;
}

.ai-briefing-inbox__item {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: #fff;
  box-shadow:
    inset 0 0 0 1px rgba(43, 93, 178, 0.1),
    0 6px 18px rgba(25, 62, 118, 0.06);
}

.ai-briefing-inbox__item.is-unread {
  box-shadow:
    inset 3px 0 0 var(--xt-primary),
    inset 0 0 0 1px rgba(43, 93, 178, 0.13),
    0 8px 22px rgba(25, 62, 118, 0.08);
}

.ai-briefing-inbox__item.is-followed {
  background: rgba(236, 253, 245, 0.92);
}

.ai-briefing-inbox__item.is-ignored {
  opacity: 0.68;
}

.ai-briefing-inbox__item-head,
.ai-briefing-inbox__meta {
  justify-content: space-between;
  gap: 8px;
}

.ai-briefing-inbox__item-head span,
.ai-briefing-inbox__item-head em,
.ai-briefing-inbox__meta span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.ai-briefing-inbox__item strong {
  color: var(--xt-text);
  font-size: 14px;
  line-height: 1.35;
}

.ai-briefing-inbox__actions {
  flex-wrap: wrap;
  gap: 6px;
}

.ai-briefing-inbox__state {
  min-height: 64px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  font-size: 13px;
}

@media (max-width: 520px) {
  .ai-briefing-inbox__filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
