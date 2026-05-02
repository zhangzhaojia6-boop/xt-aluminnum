<template>
  <section class="ai-watchlist" data-testid="ai-watchlist-panel">
    <header class="ai-watchlist__head">
      <strong>关注列表</strong>
      <span>{{ store.watchlist.length }}</span>
    </header>

    <form class="ai-watchlist__form" @submit.prevent="handleCreateWatch">
      <label>
        <span>类型</span>
        <select v-model="draft.type">
          <option v-for="type in watchTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
        </select>
      </label>
      <label>
        <span>范围</span>
        <input v-model.trim="draft.scopeKey" type="text" placeholder="factory:all" />
      </label>
      <label>
        <span>规则</span>
        <input v-model.trim="draft.triggerRules" type="text" placeholder="delay_hours_high" />
      </label>
      <button type="submit" :disabled="store.loadingWatchlist">加入关注</button>
    </form>

    <div v-if="store.loadingWatchlist && !store.watchlist.length" class="ai-watchlist__state">加载中</div>
    <div v-else-if="store.watchlist.length" class="ai-watchlist__list">
      <article v-for="watch in store.watchlist" :key="watch.id" class="ai-watchlist__item" :class="{ 'is-off': !watch.active }">
        <div>
          <strong>{{ typeLabel(watch.type) }}</strong>
          <span>{{ watch.scopeKey }}</span>
        </div>
        <em>{{ watch.frequency }}</em>
        <el-switch
          :model-value="watch.active"
          size="small"
          active-text="启用"
          inactive-text="停用"
          @change="toggleWatch(watch)"
        />
      </article>
    </div>
    <div v-else class="ai-watchlist__state">暂无关注项</div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'

import { useAssistantStore } from '../../stores/assistant'

const store = useAssistantStore()
const watchTypes = [
  { value: 'workshop', label: '车间' },
  { value: 'machine', label: '机列' },
  { value: 'coil', label: '卷' },
  { value: 'process', label: '工序' },
  { value: 'alloy_spec', label: '合金规格' },
  { value: 'metric', label: '指标' }
]
const draft = reactive({
  type: 'workshop',
  scopeKey: 'factory:all',
  triggerRules: 'delay_hours_high'
})
const typeLabelMap = computed(() => Object.fromEntries(watchTypes.map((type) => [type.value, type.label])))

onMounted(async () => {
  try {
    await store.loadWatchlist()
  } catch {
    ElMessage.error(store.lastError || '加载关注列表失败')
  }
})

function typeLabel(type) {
  return typeLabelMap.value[type] || type || '关注项'
}

async function handleCreateWatch() {
  const scopeKey = draft.scopeKey.trim()
  if (!scopeKey) return
  const triggerRules = draft.triggerRules
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  try {
    await store.createWatch({
      watch_type: draft.type,
      scope_key: scopeKey,
      trigger_rules: triggerRules.length ? triggerRules : ['delay_hours_high'],
      frequency: 'hourly',
      channels: ['in_app'],
      active: true
    })
  } catch {
    ElMessage.error(store.lastError || '创建关注失败')
  }
}

async function toggleWatch(watch) {
  if (!watch.id) return
  try {
    await store.updateWatch(watch.id, { active: !watch.active })
  } catch {
    ElMessage.error(store.lastError || '更新关注失败')
  }
}
</script>

<style scoped>
.ai-watchlist,
.ai-watchlist__list {
  display: grid;
  gap: 10px;
}

.ai-watchlist__head,
.ai-watchlist__item,
.ai-watchlist__item > div {
  display: flex;
  align-items: center;
}

.ai-watchlist__head {
  justify-content: space-between;
}

.ai-watchlist__head strong {
  color: var(--xt-text);
  font-size: 15px;
}

.ai-watchlist__head span {
  min-width: 28px;
  min-height: 24px;
  display: inline-grid;
  place-items: center;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-primary);
  font-family: var(--xt-font-number);
  font-size: 12px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.ai-watchlist__form {
  display: grid;
  grid-template-columns: minmax(92px, 0.7fr) minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  box-shadow: inset 0 0 0 1px rgba(43, 93, 178, 0.1);
}

.ai-watchlist__form label {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.ai-watchlist__form label span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.ai-watchlist__form input,
.ai-watchlist__form select {
  min-width: 0;
  min-height: 36px;
  border: 0;
  border-radius: 6px;
  background: #fff;
  color: var(--xt-text);
  font: inherit;
  font-size: 13px;
  outline: none;
  padding: 0 9px;
  box-shadow: inset 0 0 0 1px rgba(43, 93, 178, 0.13);
}

.ai-watchlist__form input:focus,
.ai-watchlist__form select:focus {
  box-shadow: var(--app-focus-ring);
}

.ai-watchlist__form button {
  align-self: end;
  min-height: 36px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.ai-watchlist__form button:active {
  transform: scale(0.96);
}

.ai-watchlist__item {
  justify-content: space-between;
  gap: 10px;
  min-height: 58px;
  padding: 9px 10px;
  border-radius: 8px;
  background: #fff;
  box-shadow:
    inset 0 0 0 1px rgba(43, 93, 178, 0.1),
    0 6px 18px rgba(25, 62, 118, 0.06);
}

.ai-watchlist__item.is-off {
  opacity: 0.64;
}

.ai-watchlist__item > div {
  min-width: 0;
  align-items: flex-start;
  flex-direction: column;
  gap: 2px;
}

.ai-watchlist__item strong,
.ai-watchlist__item span,
.ai-watchlist__item em {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-watchlist__item strong {
  color: var(--xt-text);
  font-size: 14px;
}

.ai-watchlist__item span,
.ai-watchlist__item em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.ai-watchlist__state {
  min-height: 64px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  font-size: 13px;
}

@media (max-width: 720px) {
  .ai-watchlist__form {
    grid-template-columns: 1fr;
  }
}
</style>
