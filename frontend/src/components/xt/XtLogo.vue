<template>
  <div class="xt-logo" :class="[`xt-logo--${variant}`, { 'xt-logo--color': color }]">
    <svg class="xt-logo__icon" viewBox="0 0 48 48" role="img" aria-label="鑫泰铝业">
      <path class="xt-logo__ingot" d="M24 4 40 12v20L24 44 8 32V12L24 4Z" />
      <path class="xt-logo__edge" d="M24 4v40M8 12l16 10 16-10M8 32l16-10 16 10" />
      <path class="xt-logo__core" d="M18 17.5 24 14l6 3.5v9L24 30l-6-3.5v-9Z" />
      <path class="xt-logo__flow" d="M13.5 27.5c5.2-7.8 15.8-7.8 21 0" />
      <circle class="xt-logo__node" cx="35" cy="27.5" r="2.2" />
    </svg>
    <span v-if="variant !== 'icon'" class="xt-logo__text">
      <span class="xt-logo__cn">鑫泰</span>
      <span v-if="variant === 'full'" class="xt-logo__en">ALUMINUM MES</span>
    </span>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtLogo' })

defineProps({
  variant: {
    type: String,
    default: 'full',
    validator: value => ['full', 'compact', 'icon'].includes(value)
  },
  color: {
    type: Boolean,
    default: true
  }
})
</script>

<style scoped>
.xt-logo {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
}

.xt-logo--color {
  color: var(--xt-primary);
}

.xt-logo--icon {
  gap: 0;
}

.xt-logo__icon {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  overflow: visible;
}

.xt-logo--icon .xt-logo__icon {
  width: 36px;
  height: 36px;
}

.xt-logo__ingot {
  fill: var(--xt-bg-panel);
  stroke: currentColor;
  stroke-width: 2.2;
  filter: drop-shadow(0 6px 10px rgba(11, 99, 246, 0.14));
}

.xt-logo__edge,
.xt-logo__flow {
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.xt-logo__edge {
  opacity: 0.34;
  stroke-width: 1.2;
}

.xt-logo__core {
  fill: var(--xt-accent);
  opacity: 0.92;
}

.xt-logo__flow {
  opacity: 0.72;
  stroke-width: 1.8;
}

.xt-logo__node {
  fill: var(--xt-primary);
  stroke: var(--xt-bg-panel);
  stroke-width: 1.4;
}

.xt-logo__text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  color: var(--xt-text);
}

.xt-logo__cn {
  font-size: 15px;
  font-weight: 850;
  letter-spacing: 0;
}

.xt-logo__en {
  color: var(--xt-text-secondary);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0;
}
</style>
