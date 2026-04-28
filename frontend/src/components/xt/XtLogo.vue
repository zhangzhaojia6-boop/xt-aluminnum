<template>
  <div class="xt-logo" :class="[`xt-logo--${variant}`, { 'xt-logo--color': color }]">
    <svg class="xt-logo__icon" viewBox="0 0 32 32" role="img" aria-label="鑫泰">
      <path d="M16 2 28 8v16l-12 6L4 24V8L16 2Z" fill="none" stroke="currentColor" stroke-width="1.5" />
      <path d="M16 2v28M4 8l24 16M28 8 4 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.4" />
      <path d="m10 14 6-4 6 4v8l-6 4-6-4v-8Z" fill="currentColor" opacity="0.15" />
      <path d="m10 14 6-4 6 4v8l-6 4-6-4v-8Z" fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>
    <span v-if="variant !== 'icon'" class="xt-logo__text">
      <span class="xt-logo__cn">鑫泰</span>
      <span v-if="variant === 'full'" class="xt-logo__en">XINTAI</span>
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
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
}

.xt-logo--icon .xt-logo__icon {
  width: 32px;
  height: 32px;
}

.xt-logo__text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  color: var(--xt-text);
}

.xt-logo__cn {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.xt-logo__en {
  color: var(--xt-text-secondary);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.15em;
}
</style>
