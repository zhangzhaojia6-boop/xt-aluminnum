<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <div class="xt-kpi-bar__top">
        <div class="xt-kpi-bar__label">{{ item.label }}</div>
        <span v-if="item.deltaText" class="xt-kpi-bar__delta" :class="item.deltaTone ? `tone-${item.deltaTone}` : ''">
          {{ item.deltaText }}
        </span>
      </div>
      <div class="xt-kpi-bar__value">
        <span>{{ item.value }}</span>
        <small v-if="item.unit">{{ item.unit }}</small>
      </div>
      <Sparkline
        v-if="item.spark && item.spark.length > 1"
        class="xt-kpi-bar__spark"
        :points="item.spark"
        :tone="item.sparkTone || 'primary'"
      />
      <div v-else-if="item.hint" class="xt-kpi-bar__hint">{{ item.hint }}</div>
      <div v-else class="xt-kpi-bar__hint xt-kpi-bar__hint--placeholder">&nbsp;</div>
    </li>
  </ul>
</template>

<script setup>
import Sparkline from './Sparkline.vue'
defineProps({ items: { type: Array, default: () => [] } })
</script>

<style scoped>
.xt-kpi-bar {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--xt-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (max-width: 720px) {
  .xt-kpi-bar { grid-template-columns: repeat(3, 1fr); }
}

.xt-kpi-bar__card {
  position: relative;
  display: grid;
  gap: var(--xt-space-1);
  min-height: 132px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 20%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-text-inverse) 7%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink-panel) 86%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 18px 36px color-mix(in srgb, var(--xt-bg-ink) 48%, transparent);
  overflow: hidden;
}

.xt-kpi-bar__card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--xt-primary), transparent);
  opacity: 0.8;
}

.xt-kpi-bar__card::after {
  content: '';
  position: absolute;
  right: -32px;
  bottom: -38px;
  width: 104px;
  height: 104px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--xt-primary) 16%, transparent);
  filter: blur(8px);
}

.xt-kpi-bar__card.is-muted {
  opacity: 0.55;
}

.xt-kpi-bar__top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-kpi-bar__label {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.04em;
}

.xt-kpi-bar__delta {
  border: 1px solid color-mix(in srgb, var(--xt-primary) 16%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  padding: 1px 7px;
  background: color-mix(in srgb, var(--xt-bg-panel-soft) 8%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 56%, transparent);
  font-size: 11px;
  font-weight: 850;
  font-variant-numeric: tabular-nums;
}

.xt-kpi-bar__delta.tone-positive {
  color: var(--xt-success);
  background: color-mix(in srgb, var(--xt-success-light) 10%, transparent);
  border-color: color-mix(in srgb, var(--xt-success) 40%, var(--xt-border));
}

.xt-kpi-bar__delta.tone-negative {
  color: var(--xt-danger);
  background: color-mix(in srgb, var(--xt-danger-light) 10%, transparent);
  border-color: color-mix(in srgb, var(--xt-danger) 40%, var(--xt-border));
}

.xt-kpi-bar__value {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  gap: var(--xt-space-1);
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.xt-kpi-bar__value span {
  color: var(--xt-text-inverse);
  text-shadow: 0 0 20px color-mix(in srgb, var(--xt-primary) 34%, transparent);
}

.xt-kpi-bar__value small {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-family: var(--xt-font-body);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-kpi-bar__card.tone-positive .xt-kpi-bar__value span {
  color: color-mix(in srgb, var(--xt-success) 76%, var(--xt-text-inverse));
}

.xt-kpi-bar__card.tone-negative .xt-kpi-bar__value span {
  color: color-mix(in srgb, var(--xt-danger) 76%, var(--xt-text-inverse));
}

.xt-kpi-bar__spark {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 32px;
  margin-top: 2px;
}

.xt-kpi-bar__hint {
  position: relative;
  z-index: 1;
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 750;
}

.xt-kpi-bar__hint--placeholder {
  height: 28px;
}

@media (max-width: 480px) {
  .xt-kpi-bar {
    gap: var(--xt-space-2);
  }

  .xt-kpi-bar__card {
    min-height: 120px;
    padding: var(--xt-space-2);
  }

  .xt-kpi-bar__value {
    flex-wrap: wrap;
    font-size: var(--xt-text-xl);
    line-height: 1.05;
  }

  .xt-kpi-bar__value small {
    max-width: 56px;
    line-height: 1.15;
  }
}
</style>
