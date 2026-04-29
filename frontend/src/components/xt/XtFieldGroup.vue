<template>
  <section class="xt-field-group" :class="[`xt-field-group--${tier}`, { 'is-open': open }]">
    <button
      v-if="collapsible"
      type="button"
      class="xt-field-group__head"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span>
        <strong>{{ title }}</strong>
        <small>{{ tierText }}</small>
      </span>
      <span class="xt-field-group__toggle">{{ open ? '收起' : '展开' }}</span>
    </button>
    <header v-else class="xt-field-group__head">
      <span>
        <strong>{{ title }}</strong>
        <small>{{ tierText }}</small>
      </span>
    </header>

    <div v-show="open" class="xt-field-group__grid">
      <div v-for="item in items" :key="item.key || item.label" class="xt-field-group__item">
        <span>{{ item.label }}</span>
        <strong>{{ displayValue(item.value) }}</strong>
        <em v-if="item.hint">{{ item.hint }}</em>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

defineOptions({ name: 'XtFieldGroup' })

const props = defineProps({
  title: {
    type: String,
    default: '字段'
  },
  tier: {
    type: String,
    default: 'primary',
    validator: value => ['primary', 'supporting', 'audit'].includes(value)
  },
  items: {
    type: Array,
    default: () => []
  },
  collapsed: {
    type: Boolean,
    default: false
  }
})

const open = ref(!props.collapsed && props.tier !== 'audit')
const collapsible = computed(() => props.tier !== 'primary' || props.collapsed)
const tierText = computed(() => {
  const map = {
    primary: '主字段',
    supporting: '辅助信息',
    audit: '审计来源'
  }
  return map[props.tier] || '字段'
})

watch(() => props.collapsed, value => {
  open.value = !value && props.tier !== 'audit'
})

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  return value
}
</script>

<style scoped>
.xt-field-group {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-field-group--supporting {
  background: var(--xt-bg-panel-soft);
}

.xt-field-group--audit {
  background: var(--xt-command-surface);
}

.xt-field-group__head {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.xt-field-group__head span {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.xt-field-group__head strong {
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  line-height: 1.25;
}

.xt-field-group__head small,
.xt-field-group__toggle {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-field-group__toggle {
  flex: 0 0 auto;
}

.xt-field-group__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: var(--xt-space-2);
}

.xt-field-group__item {
  min-width: 0;
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
}

.xt-field-group--primary .xt-field-group__item {
  background: var(--xt-command-surface-strong);
}

.xt-field-group__item span,
.xt-field-group__item em {
  display: block;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-style: normal;
  font-weight: 760;
  line-height: 1.4;
}

.xt-field-group__item strong {
  display: block;
  margin-top: var(--xt-space-1);
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.xt-field-group__item em {
  margin-top: 2px;
}

@media (max-width: 520px) {
  .xt-field-group {
    padding: var(--xt-space-3);
  }

  .xt-field-group__grid {
    grid-template-columns: 1fr;
  }
}
</style>
