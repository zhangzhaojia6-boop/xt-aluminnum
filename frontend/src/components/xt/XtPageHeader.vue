<template>
  <header class="xt-page-header">
    <div class="xt-page-header__main">
      <div v-if="eyebrow" class="xt-page-header__eyebrow">{{ eyebrow }}</div>
      <h1 class="xt-page-header__title">{{ title }}</h1>
      <p v-if="subTitle" class="xt-page-header__subtitle">{{ subTitle }}</p>
    </div>
    <div v-if="$slots.actions" class="xt-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
defineOptions({ name: 'XtPageHeader' })

defineProps({
  title: {
    type: String,
    required: true
  },
  subTitle: {
    type: String,
    default: ''
  },
  eyebrow: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.xt-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xt-space-6);
  margin-bottom: var(--xt-space-6);
}

.xt-page-header__main {
  min-width: 0;
}

.xt-page-header__eyebrow {
  margin-bottom: var(--xt-space-1);
  color: var(--xt-primary);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
}

.xt-page-header__title {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-2xl);
  font-weight: 800;
  line-height: 1.25;
}

.xt-page-header__subtitle {
  margin: var(--xt-space-2) 0 0;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-page-header__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--xt-space-2);
}

@media (max-width: 768px) {
  .xt-page-header {
    flex-direction: column;
  }
}
</style>
