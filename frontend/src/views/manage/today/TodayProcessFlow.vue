<template>
  <ol class="xt-flow">
    <li v-for="stage in stages" :key="stage.key" class="xt-flow__stage" :class="{ 'is-empty': isEmpty(stage) }">
      <span class="xt-flow__node">
        <svg viewBox="0 0 32 32" aria-hidden="true"><path :d="ICONS[stage.key]" /></svg>
      </span>
      <strong>{{ stage.label }}</strong>
      <b>{{ stage.primaryValue }}</b>
      <small v-if="!isEmpty(stage)">{{ stage.secondaryLabel }} {{ stage.secondaryValue }}</small>
    </li>
  </ol>
</template>

<script setup>
defineProps({ stages: { type: Array, default: () => [] } })

const ICONS = {
  casting: 'M6 22 11 10h10l5 12ZM11 10l3-4h4l3 4M6 26h20',
  'cast-roll': 'M6 16h6M20 16h6M16 6a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM16 18a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z',
  'hot-roll': 'M4 16h7M21 16h7M16 5a5 5 0 1 1 0 10 5 5 0 0 1 0-10ZM16 17a5 5 0 1 1 0 10 5 5 0 0 1 0-10ZM6 11c1-1.5-1-2.500 0-4M26 11c1-1.500-1-2.500 0-4',
  'cold-roll': 'M4 16h8M20 16h8M16 7a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM16 19a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM8 7h16M8 25h16',
  finish: 'M5 22h22M9 22V10h14v12M13 10V6h6v4M12 15h8',
  warehouse: 'M16 7a9 9 0 1 1 0 18 9 9 0 0 1 0-18ZM16 12a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM25 16h4'
}

function isEmpty(stage) {
  return stage.primaryValue === '—'
}
</script>

<style scoped>
.xt-flow { position: relative; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 16px; margin: 0; padding: 0; list-style: none; }
.xt-flow::before { content: ''; position: absolute; top: 31px; right: 8%; left: 8%; height: 2px; background: repeating-linear-gradient(90deg, var(--xt-primary) 0 14px, transparent 14px 28px); background-size: 28px 2px; opacity: 0.35; animation: xt-flow-run 1.4s linear infinite; }
.xt-flow__stage { position: relative; display: grid; justify-items: center; align-content: start; gap: 6px; min-width: 0; text-align: center; }
.xt-flow__node { display: grid; place-items: center; width: 64px; height: 64px; margin-bottom: 8px; border: 1.5px solid var(--xt-primary); border-radius: 50%; background: var(--xt-bg-page); color: var(--xt-primary); }
.xt-flow__node svg { width: 32px; height: 32px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.xt-flow__stage strong { color: var(--xt-text-secondary); font-size: 14px; font-weight: 400; }
.xt-flow__stage b { color: var(--xt-text); font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-flow__stage small { color: var(--xt-text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.is-empty .xt-flow__node { border-style: dashed; border-color: var(--xt-border); color: var(--xt-text-muted); }
.is-empty b { color: var(--xt-text-muted); font-weight: 400; }
@keyframes xt-flow-run { to { background-position-x: 28px; } }
@media (max-width: 860px) {
  .xt-flow { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .xt-flow::before { top: 16px; right: auto; bottom: 16px; left: 23px; width: 2px; height: auto; background: repeating-linear-gradient(180deg, var(--xt-primary) 0 14px, transparent 14px 28px); background-size: 2px 28px; animation: none; }
  .xt-flow__stage { grid-template-columns: 48px minmax(0, 1fr) auto; justify-items: start; align-items: center; gap: 0 16px; padding: 8px 0; text-align: left; }
  .xt-flow__node { width: 48px; height: 48px; margin: 0; }
  .xt-flow__node svg { width: 24px; height: 24px; }
  .xt-flow__stage b { font-size: 20px; }
  .xt-flow__stage small { grid-column: 2 / -1; }
}
@media (prefers-reduced-motion: reduce) {
  .xt-flow::before { animation: none; }
}
</style>
