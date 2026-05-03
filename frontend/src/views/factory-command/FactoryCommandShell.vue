<template>
  <section class="factory-command-shell">
    <header class="factory-command-shell__head">
      <div>
        <span class="factory-command-shell__system">鑫泰铝业 数据中枢</span>
        <h1>{{ title }}</h1>
      </div>
      <div class="factory-command-shell__sync">
        <span>数据源 {{ sourceLabel(freshness?.source || 'mes_projection') }}</span>
        <span>最后同步 {{ formatSyncTime(freshness?.last_synced_at) }}</span>
        <strong :class="`is-${freshness?.status || 'idle'}`">{{ freshnessLabel(freshness?.status, freshness) }}</strong>
      </div>
    </header>

    <nav class="factory-command-shell__tabs" aria-label="工厂指挥导航">
      <RouterLink v-for="tab in tabs" :key="tab.path" :to="tab.path" :class="{ 'is-active': tab.key === active }">
        {{ tab.label }}
      </RouterLink>
    </nav>

    <main class="factory-command-shell__body">
      <slot />
    </main>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'

import { formatSyncTime, freshnessLabel, sourceLabel } from '../../utils/factoryCommandFormatters'

defineProps({
  title: { type: String, required: true },
  active: { type: String, required: true },
  freshness: { type: Object, default: () => ({}) }
})

const tabs = [
  { key: 'overview', label: '工厂总览', path: '/manage/overview' },
  { key: 'flow', label: '生产流转', path: '/manage/factory/flow' },
  { key: 'machine-lines', label: '车间机列', path: '/manage/factory/machine-lines' },
  { key: 'coils', label: '卷级追踪', path: '/manage/factory/coils' },
  { key: 'cost', label: '经营效益', path: '/manage/factory/cost' },
  { key: 'destinations', label: '库存去向', path: '/manage/factory/destinations' },
  { key: 'exceptions', label: '异常地图', path: '/manage/factory/exceptions' }
]
</script>

<style scoped>
.factory-command-shell {
  --fc-blue: oklch(54% 0.19 255);
  --fc-green: oklch(53% 0.13 158);
  --fc-amber: oklch(62% 0.12 75);
  --fc-red: oklch(55% 0.15 28);
  --fc-ink: oklch(18% 0.024 252);
  --fc-line: rgba(43, 93, 178, 0.13);
  display: grid;
  gap: 12px;
}

.factory-command-shell__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--fc-line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 44px rgba(25, 62, 118, 0.08);
}

.factory-command-shell__system {
  color: var(--fc-blue);
  font-size: 12px;
  font-weight: 850;
}

.factory-command-shell h1 {
  margin: 3px 0 0;
  color: var(--fc-ink);
  font-size: 24px;
  font-weight: 900;
  letter-spacing: 0;
}

.factory-command-shell__sync {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.factory-command-shell__sync span,
.factory-command-shell__sync strong {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid var(--fc-line);
  border-radius: 6px;
  background: #fff;
}

.factory-command-shell__sync strong.is-fresh {
  color: var(--fc-green);
}

.factory-command-shell__sync strong.is-stale {
  color: var(--fc-amber);
}

.factory-command-shell__sync strong.is-unconfigured,
.factory-command-shell__sync strong.is-idle {
  color: var(--xt-text-secondary);
}

.factory-command-shell__sync strong.is-migration_missing,
.factory-command-shell__sync strong.is-failed,
.factory-command-shell__sync strong.is-offline_or_blocked {
  color: var(--fc-red);
}

.factory-command-shell__tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 6px;
  border: 1px solid var(--fc-line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.88);
}

.factory-command-shell__tabs a {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 6px;
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 850;
  text-decoration: none;
  white-space: nowrap;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.factory-command-shell__tabs a:active {
  transform: scale(0.96);
}

.factory-command-shell__tabs a.is-active {
  background: var(--fc-blue);
  color: #fff;
}

.factory-command-shell__body {
  min-width: 0;
}

@media (max-width: 760px) {
  .factory-command-shell__head {
    align-items: stretch;
    flex-direction: column;
  }

  .factory-command-shell__sync {
    justify-content: flex-start;
  }
}
</style>
