<template>
  <svg
    v-if="ready"
    class="xt-spark"
    :class="`tone-${tone}`"
    :viewBox="`0 0 ${vbW} ${vbH}`"
    preserveAspectRatio="none"
    role="img"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="gradId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="strokeColor" stop-opacity="0.28" />
        <stop offset="100%" :stop-color="strokeColor" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path :d="areaD" :fill="`url(#${gradId})`" />
    <path :d="lineD" fill="none" :stroke="strokeColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
    <circle :cx="lastX" :cy="lastY" r="2.4" :fill="strokeColor" />
  </svg>
  <div v-else class="xt-spark xt-spark--empty" />
</template>

<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  points: { type: Array, default: () => [] },
  tone: { type: String, default: 'primary' }
})

const vbW = 100
const vbH = 28

const ready = computed(() => Array.isArray(props.points) && props.points.length > 1)

const _uid = useId()
const gradId = computed(() => `xt-spark-grad-${_uid}`)

const strokeColor = computed(() => {
  switch (props.tone) {
    case 'success': return 'var(--xt-success, #3ba55c)'
    case 'warning': return 'var(--xt-warning, #cc8a1f)'
    case 'danger': return 'var(--xt-danger, #d65241)'
    case 'muted': return 'var(--xt-text-muted, #94a3b8)'
    default: return 'var(--xt-primary, #1f6feb)'
  }
})

function buildPaths(points) {
  const valid = points.filter((v) => Number.isFinite(v))
  if (valid.length < 2) return { line: '', area: '', lastX: 0, lastY: 0 }
  const min = Math.min(...valid)
  const max = Math.max(...valid)
  const span = max - min || 1
  const step = vbW / (points.length - 1)
  const padTop = 3
  const padBot = 3
  const usable = vbH - padTop - padBot
  const coords = points.map((v, i) => {
    const x = i * step
    const norm = Number.isFinite(v) ? (v - min) / span : 0
    const y = padTop + (1 - norm) * usable
    return [x, y]
  })
  const line = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'}${c[0].toFixed(2)},${c[1].toFixed(2)}`)
    .join(' ')
  const area = `${line} L${coords[coords.length - 1][0].toFixed(2)},${vbH} L0,${vbH} Z`
  const last = coords[coords.length - 1]
  return { line, area, lastX: last[0], lastY: last[1] }
}

const paths = computed(() => buildPaths(props.points))
const lineD = computed(() => paths.value.line)
const areaD = computed(() => paths.value.area)
const lastX = computed(() => paths.value.lastX)
const lastY = computed(() => paths.value.lastY)
</script>

<style scoped>
.xt-spark { display: block; width: 100%; height: 100%; }
.xt-spark--empty { background: transparent; }
</style>
