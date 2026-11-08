<template>
  <svg v-if="line" class="xt-spark" viewBox="0 0 240 72" preserveAspectRatio="none" role="img" :aria-label="label">
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="var(--xt-primary)" stop-opacity="0.18" />
        <stop offset="1" stop-color="var(--xt-primary)" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path class="xt-spark__area" :d="area" :fill="`url(#${gradientId})`" />
    <path class="xt-spark__line" :d="line" pathLength="1" vector-effect="non-scaling-stroke" />
  </svg>
</template>

<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  points: { type: Array, default: () => [] },
  label: { type: String, default: '' }
})

const gradientId = useId()
const coords = computed(() => {
  const known = props.points
    .map((value, index) => ({ value: Number(value), index, missing: value === null || value === undefined }))
    .filter((point) => !point.missing && Number.isFinite(point.value))
  if (known.length < 2) return []
  const values = known.map((point) => point.value)
  const min = Math.min(...values)
  const span = Math.max(...values) - min || 1
  const step = 240 / Math.max(props.points.length - 1, 1)
  return known.map((point) => [point.index * step, 66 - ((point.value - min) / span) * 58])
})
const line = computed(() => coords.value.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' '))
const area = computed(() => {
  if (!coords.value.length) return ''
  const first = coords.value[0][0].toFixed(1)
  const last = coords.value[coords.value.length - 1][0].toFixed(1)
  return `${line.value} L${last} 72 L${first} 72 Z`
})
</script>

<style scoped>
.xt-spark { display: block; width: 100%; height: 72px; overflow: visible; }
.xt-spark__line { fill: none; stroke: var(--xt-primary); stroke-width: 2; stroke-dasharray: 1; stroke-dashoffset: 1; animation: xt-spark-draw 1100ms cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.xt-spark__area { opacity: 0; animation: xt-spark-fade 700ms 500ms ease-out forwards; }
@keyframes xt-spark-draw { to { stroke-dashoffset: 0; } }
@keyframes xt-spark-fade { to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .xt-spark__line { animation: none; stroke-dashoffset: 0; }
  .xt-spark__area { animation: none; opacity: 1; }
}
</style>
