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
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 9px;
  background: transparent;

}

.live-data-state-panel span {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  border: 1px solid var(--xt-border);
  border-radius: 999px;
  background: transparent;
  padding: 7px 11px;
}

.live-data-state-panel span::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;

  content: "";
}

.live-data-state-panel b {
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.live-data-state-panel em {
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-style: normal;
  font-size: 12px;
}

.live-data-state-panel .is-warning { color: var(--xt-warning); }
.live-data-state-panel .is-danger { color: var(--xt-text); }
.live-data-state-panel .is-success { color: var(--xt-primary); }
.live-data-state-panel .is-muted { color: var(--xt-text); }

</style>
