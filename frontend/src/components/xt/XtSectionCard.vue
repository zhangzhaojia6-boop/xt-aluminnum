<template>
  <section class="xt-section-card" :class="{ 'xt-section-card--collapsed': collapsed }">
    <header class="xt-section-card__header" @click="toggleable && toggle()">
      <div class="xt-section-card__heading">
        <h3 class="xt-section-card__title">{{ title }}</h3>
        <span v-if="badge" class="xt-section-card__badge">{{ badge }}</span>
      </div>
      <div class="xt-section-card__toolbar">
        <slot name="toolbar" />
        <button v-if="toggleable" class="xt-section-card__toggle" aria-label="Toggle section">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </header>
    <div v-show="!collapsed" class="xt-section-card__body">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineOptions({ name: 'XtSectionCard' })

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  badge: {
    type: [String, Number],
    default: ''
  },
  toggleable: {
    type: Boolean,
    default: false
  },
  defaultCollapsed: {
    type: Boolean,
    default: false
  }
})

const collapsed = ref(props.defaultCollapsed)
const toggle = () => { collapsed.value = !collapsed.value }

defineExpose({ collapsed, toggle })
</script>

<style scoped>
.xt-section-card {
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-section-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--xt-space-4) var(--xt-space-5);
  border-bottom: 1px solid var(--xt-border-light);
  cursor: default;
}

.xt-section-card--collapsed .xt-section-card__header {
  border-bottom-color: transparent;
}

.xt-section-card__heading {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-section-card__title {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-base);
  font-weight: 800;
  letter-spacing: -0.01em;
}

.xt-section-card__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 var(--xt-space-2);
  border-radius: var(--xt-radius-full);
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-section-card__toolbar {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-section-card__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: var(--xt-radius-sm);
  background: transparent;
  color: var(--xt-text-muted);
  cursor: pointer;
  transition: transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-section-card--collapsed .xt-section-card__toggle {
  transform: rotate(-90deg);
}

.xt-section-card__body {
  padding: var(--xt-space-5);
}
</style>
