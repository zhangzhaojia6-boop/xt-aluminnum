<template>
  <i class="xt-pulse" :class="`is-${state}`" aria-hidden="true" />
</template>

<script setup>
defineOptions({ name: 'XtPulseDot' })

defineProps({
  state: { type: String, default: 'stale' }
})
</script>

<style scoped>
.xt-pulse { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--xt-warning); flex: none; }
.xt-pulse.is-live { background: var(--xt-success); animation: xt-pulse-breathe 2s ease-in-out infinite; }
.xt-pulse.is-offline { background: var(--xt-danger); }
@keyframes xt-pulse-breathe { 50% { opacity: 0.4; } }
@media (prefers-reduced-motion: reduce) {
  .xt-pulse.is-live { animation: none; }
}
</style>
