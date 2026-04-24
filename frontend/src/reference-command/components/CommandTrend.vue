<template>
  <svg class="cmd-trend" viewBox="0 0 220 80" role="img" aria-label="趋势">
    <polyline :points="polylinePoints" fill="none" stroke="#1f6fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    <g fill="#1f6fff">
      <circle v-for="(point, index) in pointList" :key="index" :cx="point.x" :cy="point.y" r="3" />
    </g>
    <g fill="#d8e6fb">
      <rect v-for="(bar, index) in bars" :key="index" :x="bar.x" :y="bar.y" width="10" :height="bar.height" rx="2" />
    </g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  values: {
    type: Array,
    default: () => [18, 24, 21, 33, 29, 36, 41, 35]
  }
})

const pointList = computed(() => {
  const values = props.values.length ? props.values.map((value) => Number(value) || 0) : [0]
  const max = Math.max(...values, 1)
  const step = values.length > 1 ? 190 / (values.length - 1) : 190
  return values.map((value, index) => ({
    x: 15 + index * step,
    y: 66 - (value / max) * 50
  }))
})

const polylinePoints = computed(() => pointList.value.map((point) => `${point.x},${point.y}`).join(' '))

const bars = computed(() => pointList.value.map((point) => ({
  x: point.x - 5,
  y: Math.min(point.y + 8, 66),
  height: Math.max(4, 66 - Math.min(point.y + 8, 66))
})))
</script>
