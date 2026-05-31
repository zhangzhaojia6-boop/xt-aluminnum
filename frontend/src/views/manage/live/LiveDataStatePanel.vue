<template>
  <section class="live-data-state-panel" aria-label="数据状态">
    <span v-for="state in states" :key="state.label" :class="`is-${state.tone}`">
      <b>{{ state.label }}</b>
      <em>{{ state.value }}</em>
    </span>
  </section>
</template>

<script setup>
defineProps({
  states: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.live-data-state-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 12px;
  padding: 9px;
  background:
    linear-gradient(90deg, rgba(4, 22, 42, 0.82), rgba(7, 38, 66, 0.6)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.live-data-state-panel span {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 999px;
  background: rgba(1, 16, 31, 0.72);
  padding: 7px 11px;
}

.live-data-state-panel span::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 12px currentcolor;
  content: "";
  animation: liveStatePulse 1.6s ease-in-out infinite;
}

.live-data-state-panel b {
  color: rgba(185, 223, 235, 0.7);
  font-size: 12px;
}

.live-data-state-panel em {
  color: rgba(225, 253, 255, 0.9);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-style: normal;
  font-size: 12px;
}

.live-data-state-panel .is-warning { color: #ffab00; }
.live-data-state-panel .is-danger { color: #ff5d4d; }
.live-data-state-panel .is-success { color: #00f2ff; }
.live-data-state-panel .is-muted { color: #7aa2bd; }

@keyframes liveStatePulse {
  0%, 100% { opacity: 0.52; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .live-data-state-panel span::before {
    animation: none;
  }
}
</style>
