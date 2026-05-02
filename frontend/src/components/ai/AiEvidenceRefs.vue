<template>
  <section class="ai-evidence" data-testid="ai-evidence-refs">
    <header class="ai-evidence__head">
      <strong>证据</strong>
      <span>{{ normalizedRefs.length }}</span>
    </header>

    <div v-if="normalizedRefs.length" class="ai-evidence__list">
      <span v-for="ref in normalizedRefs" :key="`${ref.kind}:${ref.key}`" class="ai-evidence__ref">
        <em>{{ ref.kind }}</em>
        <span>{{ ref.label || ref.key }}</span>
      </span>
    </div>
    <div v-else class="ai-evidence__empty">暂无证据</div>

    <div v-if="normalizedMissingData.length" class="ai-evidence__missing">
      <strong>缺失数据</strong>
      <span v-for="item in normalizedMissingData" :key="item">{{ item }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  refs: {
    type: Array,
    default: () => []
  },
  missingData: {
    type: Array,
    default: () => []
  }
})

const normalizedRefs = computed(() => {
  return props.refs
    .map((item) => ({
      kind: item?.kind || item?.type || 'source',
      key: item?.key || item?.id || '',
      label: item?.label || ''
    }))
    .filter((item) => item.key)
})
const normalizedMissingData = computed(() => props.missingData.filter(Boolean))
</script>

<style scoped>
.ai-evidence {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  box-shadow: inset 0 0 0 1px rgba(43, 93, 178, 0.1);
}

.ai-evidence__head,
.ai-evidence__ref,
.ai-evidence__missing {
  display: flex;
  align-items: center;
}

.ai-evidence__head {
  justify-content: space-between;
  color: var(--xt-text);
  font-size: 13px;
}

.ai-evidence__head span {
  min-width: 24px;
  min-height: 24px;
  display: inline-grid;
  place-items: center;
  border-radius: var(--xt-radius-pill);
  background: #fff;
  color: var(--xt-primary);
  font-family: var(--xt-font-number);
  font-size: 12px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.ai-evidence__list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-evidence__ref {
  max-width: 100%;
  gap: 6px;
  min-height: 28px;
  padding: 0 8px;
  border-radius: 6px;
  background: #fff;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.ai-evidence__ref em {
  color: var(--xt-primary);
  font-style: normal;
}

.ai-evidence__ref span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-evidence__empty {
  color: var(--xt-text-muted);
  font-size: 12px;
}

.ai-evidence__missing {
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid rgba(43, 93, 178, 0.1);
}

.ai-evidence__missing strong,
.ai-evidence__missing span {
  font-size: 12px;
}

.ai-evidence__missing strong {
  color: var(--xt-text-secondary);
}

.ai-evidence__missing span {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 7px;
  border-radius: 6px;
  background: rgba(255, 247, 237, 0.94);
  color: var(--xt-warning);
  font-weight: 850;
}
</style>
