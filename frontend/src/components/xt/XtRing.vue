<template>
  <svg class="xt-ring" :class="{ 'is-empty': !arc.hasArc }" viewBox="0 0 48 48" role="img" :aria-label="label">
    <circle class="xt-ring__track" cx="24" cy="24" r="20" />
    <circle v-if="arc.hasArc" class="xt-ring__arc" cx="24" cy="24" r="20" :stroke-dasharray="arc.dash" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

import { ringArc } from '../../utils/ring-arc.js'

defineOptions({ name: 'XtRing' })

const props = defineProps({
  ratio: { type: [Number, String], default: null },
  label: { type: String, default: '' }
})

const arc = computed(() => ringArc(props.ratio))
</script>

<style scoped>
.xt-ring { width: 56px; height: 56px; transform: rotate(-90deg); }
.xt-ring__track { fill: none; stroke: var(--xt-border); stroke-width: 4; }
.xt-ring__arc { fill: none; stroke: var(--xt-primary); stroke-width: 4; stroke-linecap: round; animation: xt-ring-in 800ms var(--xt-ease, ease-out) both; }
@keyframes xt-ring-in { from { stroke-dasharray: 0 126; } }
@media (prefers-reduced-motion: reduce) {
  .xt-ring__arc { animation: none; }
}
</style>
