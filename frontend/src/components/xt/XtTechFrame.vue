<template>
  <div class="xt-tech-frame">
    <i class="xt-tech-frame__corner is-tl" aria-hidden="true" />
    <i class="xt-tech-frame__corner is-tr" aria-hidden="true" />
    <i class="xt-tech-frame__corner is-bl" aria-hidden="true" />
    <i class="xt-tech-frame__corner is-br" aria-hidden="true" />
    <slot />
  </div>
</template>

<script setup>
defineOptions({ name: 'XtTechFrame' })
</script>

<style scoped>
.xt-tech-frame { position: relative; padding: 20px 24px; }
.xt-tech-frame__corner { position: absolute; width: 12px; height: 12px; border: 0 solid var(--xt-border-strong); pointer-events: none; }
.xt-tech-frame__corner.is-tl { top: 0; left: 0; border-top-width: 1px; border-left-width: 1px; }
.xt-tech-frame__corner.is-tr { top: 0; right: 0; border-top-width: 1px; border-right-width: 1px; }
.xt-tech-frame__corner.is-bl { bottom: 0; left: 0; border-bottom-width: 1px; border-left-width: 1px; }
.xt-tech-frame__corner.is-br { bottom: 0; right: 0; border-bottom-width: 1px; border-right-width: 1px; }
</style>
