<template>
  <ul class="xt-bars">
    <li v-for="(row, index) in bars" :key="row.key" :title="`月累计 ${row.monthlyOutputText} · 比昨日 ${row.deltaText}`">
      <span class="xt-bars__name">{{ row.workshop }}</span>
      <span class="xt-bars__track">
        <i v-if="row.ratio" :style="{ width: `${row.ratio * 100}%`, animationDelay: `${index * 60}ms` }" />
      </span>
      <b :class="{ 'is-empty': !row.ratio }">{{ row.ratio ? row.dailyOutputText : '暂无' }}</b>
    </li>
  </ul>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ rows: { type: Array, default: () => [] } })

const bars = computed(() => {
  const max = Math.max(...props.rows.map((row) => row.dailyValue || 0), 0)
  return props.rows.map((row) => ({ ...row, ratio: max > 0 ? (row.dailyValue || 0) / max : 0 }))
})
</script>

<style scoped>
.xt-bars { display: grid; gap: 16px; margin: 0; padding: 0; list-style: none; }
.xt-bars li { display: grid; grid-template-columns: 80px minmax(0, 1fr) 88px; align-items: center; gap: 16px; }
.xt-bars__name { overflow: hidden; color: var(--xt-text-secondary); text-overflow: ellipsis; white-space: nowrap; }
.xt-bars__track { display: block; height: 12px; border-radius: 2px; background: var(--xt-bg-panel-soft); }
.xt-bars__track i { display: block; height: 100%; border-radius: 2px; background: var(--xt-primary); transform-origin: left; animation: xt-bar-grow 800ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
.xt-bars b { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.xt-bars b.is-empty { color: var(--xt-text-muted); font-weight: 400; }
@keyframes xt-bar-grow { from { transform: scaleX(0); } }
@media (prefers-reduced-motion: reduce) {
  .xt-bars__track i { animation: none; }
}
</style>
