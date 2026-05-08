<template>
  <section class="fc-shell">
    <div class="fc-shell__grid"></div>
    <header class="fc-shell__head">
      <div class="fc-shell__brand">
        <span class="fc-shell__system">鑫泰铝业 数据中枢</span>
        <h1>{{ title }}</h1>
      </div>
      <nav class="fc-shell__tabs" aria-label="工厂指挥导航">
        <RouterLink v-for="tab in tabs" :key="tab.path" :to="tab.path" :class="{ 'is-active': tab.key === active }">
          {{ tab.label }}
        </RouterLink>
      </nav>
      <div class="fc-shell__sync">
        <span>{{ sourceLabel(freshness?.source || 'mes_projection') }}</span>
        <span>{{ formatSyncTime(freshness?.last_synced_at) }}</span>
        <strong :class="`is-${freshness?.status || 'idle'}`">{{ freshnessLabel(freshness?.status, freshness) }}</strong>
      </div>
    </header>

    <main class="fc-shell__body">
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
  { key: 'overview', label: '总览', path: '/manage/overview' },
  { key: 'flow', label: '流转', path: '/manage/factory/flow' },
  { key: 'machine-lines', label: '机列', path: '/manage/factory/machine-lines' },
  { key: 'exceptions', label: '异常', path: '/manage/factory/exceptions' }
]
</script>

<style scoped>
.fc-shell {
  --fc-bg: oklch(14% 0.02 252);
  --fc-surface: oklch(18% 0.022 252);
  --fc-surface-raised: oklch(21% 0.024 252);
  --fc-blue: oklch(62% 0.18 255);
  --fc-blue-dim: oklch(45% 0.12 255);
  --fc-green: oklch(62% 0.14 158);
  --fc-amber: oklch(68% 0.14 75);
  --fc-red: oklch(60% 0.16 28);
  --fc-text: oklch(92% 0.01 252);
  --fc-text-dim: oklch(62% 0.02 252);
  --fc-line: oklch(28% 0.03 252);
  --fc-glow: rgba(80, 160, 255, 0.08);
  position: relative;
  display: grid;
  gap: 0;
  min-height: 100vh;
  padding: 12px;
  background: var(--fc-bg);
  color: var(--fc-text);
  font-family: 'MiSans', 'Inter', system-ui, sans-serif;
}

.fc-shell__grid {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, oklch(22% 0.04 255 / 0.12) 1px, transparent 1px),
    linear-gradient(oklch(22% 0.04 255 / 0.08) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,0.3) 0%, transparent 70%);
}

.fc-shell__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 20px;
  background: var(--fc-surface);
  border: 1px solid var(--fc-line);
  border-radius: 12px;
  margin-bottom: 12px;
}

.fc-shell__brand {
  flex-shrink: 0;
}

.fc-shell__system {
  display: block;
  color: var(--fc-blue);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.fc-shell h1 {
  margin: 2px 0 0;
  color: var(--fc-text);
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.01em;
}

.fc-shell__tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  background: oklch(16% 0.018 252);
  border: 1px solid var(--fc-line);
  border-radius: 8px;
}

.fc-shell__tabs a {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  padding: 0 14px;
  border-radius: 6px;
  color: var(--fc-text-dim);
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
  transition: all 120ms cubic-bezier(0.16, 1, 0.3, 1);
}

.fc-shell__tabs a:active {
  transform: scale(0.96);
}

@media (hover: hover) {
  .fc-shell__tabs a:not(.is-active):hover {
    color: var(--fc-text);
    background: oklch(24% 0.03 255);
  }
}

.fc-shell__tabs a.is-active {
  background: var(--fc-blue);
  color: oklch(100% 0 0);
  box-shadow: 0 0 12px oklch(62% 0.18 255 / 0.4);
}

.fc-shell__sync {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--fc-text-dim);
}

.fc-shell__sync span,
.fc-shell__sync strong {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  border: 1px solid var(--fc-line);
  border-radius: 5px;
  background: oklch(16% 0.015 252);
}

.fc-shell__sync strong.is-fresh { color: var(--fc-green); }
.fc-shell__sync strong.is-stale { color: var(--fc-amber); }
.fc-shell__sync strong.is-unconfigured,
.fc-shell__sync strong.is-idle { color: var(--fc-text-dim); }
.fc-shell__sync strong.is-migration_missing,
.fc-shell__sync strong.is-failed,
.fc-shell__sync strong.is-offline_or_blocked { color: var(--fc-red); }

.fc-shell__body {
  position: relative;
  z-index: 1;
  min-width: 0;
}

@media (max-width: 900px) {
  .fc-shell__head {
    flex-wrap: wrap;
  }
  .fc-shell__sync {
    margin-left: 0;
    width: 100%;
  }
}

@media (max-width: 600px) {
  .fc-shell {
    padding: 8px;
  }
  .fc-shell__head {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 12px;
  }
  .fc-shell__tabs {
    overflow-x: auto;
  }
}
</style>
