<template>
  <span class="animated-metric-value" :class="{ 'is-rolling': rolling }">{{ displayValue }}</span>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  value: {
    type: [String, Number],
    default: '0',
  },
})

const displayValue = ref(String(props.value ?? '0'))
const rolling = ref(false)
let frameId = 0

function parseMetric(value) {
  const text = String(value ?? '0')
  const match = text.match(/-?\d[\d,]*(?:\.\d+)?/)
  if (!match) return null
  const raw = match[0]
  const numeric = Number(raw.replace(/,/g, ''))
  if (!Number.isFinite(numeric)) return null
  return {
    text,
    numeric,
    decimals: raw.includes('.') ? raw.split('.')[1].length : 0,
    start: match.index || 0,
    end: (match.index || 0) + raw.length,
  }
}

function formatNumber(value, decimals) {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function animateValue(nextValue, previousValue) {
  if (frameId && typeof window !== 'undefined') window.cancelAnimationFrame(frameId)
  const next = parseMetric(nextValue)
  const previous = parseMetric(previousValue)
  if (!next || !previous || prefersReducedMotion() || typeof window === 'undefined') {
    displayValue.value = String(nextValue ?? '0')
    rolling.value = false
    return
  }
  const startValue = previous.numeric
  const delta = next.numeric - startValue
  const startAt = performance.now()
  const durationMs = 1000
  rolling.value = true

  const step = (now) => {
    const progress = Math.min(1, (now - startAt) / durationMs)
    const eased = 1 - Math.pow(1 - progress, 3)
    const current = startValue + delta * eased
    displayValue.value = `${next.text.slice(0, next.start)}${formatNumber(current, next.decimals)}${next.text.slice(next.end)}`
    if (progress < 1) {
      frameId = window.requestAnimationFrame(step)
      return
    }
    displayValue.value = String(nextValue ?? '0')
    rolling.value = false
  }

  frameId = window.requestAnimationFrame(step)
}

watch(
  () => props.value,
  (nextValue, previousValue) => {
    if (previousValue === undefined) {
      displayValue.value = String(nextValue ?? '0')
      return
    }
    animateValue(nextValue, previousValue)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (frameId && typeof window !== 'undefined') window.cancelAnimationFrame(frameId)
})
</script>

<style scoped>
.animated-metric-value {
  display: inline-block;
  min-width: 0;
  font-variant-numeric: tabular-nums;
}

.animated-metric-value.is-rolling {
  color: #74f5ff;
}

@media (prefers-reduced-motion: reduce) {
  .animated-metric-value {
    transition: none;
  }
}
</style>
