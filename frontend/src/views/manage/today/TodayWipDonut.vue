<template>
  <div class="xt-donut">
    <div class="xt-donut__chart">
      <svg viewBox="0 0 120 120" role="img" :aria-label="`在制料合计 ${totalText}`">
        <circle
          v-for="slice in slices"
          :key="slice.key"
          cx="60"
          cy="60"
          r="50"
          pathLength="100"
          :stroke="slice.color"
          :stroke-dasharray="drawn ? `${slice.share} 100` : '0 100'"
          :stroke-dashoffset="-slice.offset"
        />
      </svg>
      <div class="xt-donut__total">
        <b>{{ totalText }}</b>
      </div>
    </div>
    <ul class="xt-donut__legend">
      <li v-for="slice in slices" :key="slice.key">
        <i :style="{ background: slice.color }" />
        <span>{{ slice.title }}</span>
        <b>{{ slice.weightText }}</b>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  totalText: { type: String, default: '' }
})

const COLORS = ['#003890', '#2f5ea8', '#5f83bd', '#8fa9d2', '#bccde6', '#d1d5db']
const TOP = 5
const drawn = ref(false)

const slices = computed(() => {
  const known = props.rows.filter((row) => (row.totalWeight || 0) > 0).sort((a, b) => b.totalWeight - a.totalWeight)
  const total = known.reduce((sum, row) => sum + row.totalWeight, 0)
  if (!total) return []
  const head = known.slice(0, TOP)
  const rest = known.slice(TOP)
  const items = [...head]
  if (rest.length) {
    const weight = rest.reduce((sum, row) => sum + row.totalWeight, 0)
    items.push({ key: 'rest', title: `其他 ${rest.length} 处`, totalWeight: weight, weightText: `${weight.toLocaleString('zh-CN', { maximumFractionDigits: 1 })} 吨` })
  }
  let offset = 0
  return items.map((row, index) => {
    const share = (row.totalWeight / total) * 100
    const slice = { key: row.key, title: row.title, weightText: row.weightText, share, offset, color: COLORS[index] }
    offset += share
    return slice
  })
})

onMounted(() => {
  requestAnimationFrame(() => { drawn.value = true })
})
</script>

<style scoped>
.xt-donut { display: grid; grid-template-columns: 160px minmax(0, 1fr); align-items: center; gap: 32px; }
.xt-donut__chart { position: relative; }
.xt-donut__chart svg { display: block; width: 100%; transform: rotate(-90deg); }
.xt-donut__chart circle { fill: none; stroke-width: 14; transition: stroke-dasharray 1000ms cubic-bezier(0.16, 1, 0.3, 1); }
.xt-donut__total { position: absolute; inset: 0; display: grid; place-items: center; text-align: center; }
.xt-donut__total b { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-donut__legend { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.xt-donut__legend li { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.xt-donut__legend i { width: 10px; height: 10px; border-radius: 2px; }
.xt-donut__legend span { overflow: hidden; color: var(--xt-text-secondary); text-overflow: ellipsis; white-space: nowrap; }
.xt-donut__legend b { font-weight: 400; font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) {
  .xt-donut__chart circle { transition: none; }
}
@media (max-width: 480px) {
  .xt-donut { grid-template-columns: minmax(0, 1fr); justify-items: stretch; }
  .xt-donut__chart { width: 160px; margin: 0 auto; }
}
</style>
