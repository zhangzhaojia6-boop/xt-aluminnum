<template>
  <section class="xt-card" :class="[`xt-card--${padding}`, { 'xt-card--interactive': interactive }]">
    <header v-if="title || subTitle || $slots.header || $slots.actions" class="xt-card__header">
      <slot name="header">
        <div class="xt-card__heading">
          <h2 v-if="title" class="xt-card__title">{{ title }}</h2>
          <p v-if="subTitle" class="xt-card__subtitle">{{ subTitle }}</p>
        </div>
      </slot>
      <div v-if="$slots.actions" class="xt-card__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="xt-card__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="xt-card__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup>
defineOptions({ name: 'XtCard' })

defineProps({
  title: {
    type: String,
    default: ''
  },
  subTitle: {
    type: String,
    default: ''
  },
  padding: {
    type: String,
    default: 'normal',
    validator: value => ['none', 'small', 'normal', 'large'].includes(value)
  },
  interactive: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.xt-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  box-shadow: var(--xt-shadow-inset-hairline);
}

.xt-card--interactive {
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .xt-card--interactive:hover {
    border-color: var(--xt-border);
    box-shadow: var(--xt-shadow-md);
    transform: translateY(-1px);
  }
}

.xt-card__header,
.xt-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4) var(--xt-space-5);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-card__footer {
  border-top: 1px solid var(--xt-border-light);
  border-bottom: 0;
}

.xt-card__heading {
  min-width: 0;
}

.xt-card__title {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  line-height: 1.35;
  letter-spacing: 0;
}

.xt-card__subtitle {
  margin: var(--xt-space-1) 0 0;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-card__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-card__body {
  padding: var(--xt-space-5);
}

.xt-card--none .xt-card__body {
  padding: 0;
}

.xt-card--small .xt-card__body {
  padding: var(--xt-space-3);
}

.xt-card--large .xt-card__body {
  padding: var(--xt-space-6);
}
</style>
