<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <div class="xt-kpi-bar__content">
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
        <div v-if="item.sourceLabel" class="xt-kpi-bar__source">{{ item.sourceLabel }}</div>
        <Sparkline
          v-if="item.spark && item.spark.length > 1"
          class="xt-kpi-bar__spark"
          :points="item.spark"
          :tone="item.sparkTone || 'primary'"
        />
        <div v-else-if="item.hint" class="xt-kpi-bar__hint">{{ item.hint }}</div>
        <div v-else class="xt-kpi-bar__hint xt-kpi-bar__hint--placeholder">&nbsp;</div>
      </div>
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
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (max-width: 1180px) {
  .xt-kpi-bar { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 720px) {
  .xt-kpi-bar { grid-template-columns: repeat(2, 1fr); }
}

.xt-kpi-bar__card {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 11px;
  align-items: start;
  min-height: 98px;
  padding: 11px 12px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;

  overflow: hidden;
}

.xt-kpi-bar__card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: transparent;
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
  background: transparent;
}

.xt-kpi-bar__card.is-muted {
  opacity: 0.55;
}

.xt-kpi-bar__top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-kpi-bar__content {
  position: relative;
  z-index: 1;
  min-width: 0;
}

.xt-kpi-bar__icon {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.xt-kpi-bar__icon i,
.xt-kpi-bar__icon::before,
.xt-kpi-bar__icon::after {
  content: '';
  position: absolute;
  display: block;
}

.xt-kpi-bar__icon i {
  width: 22px;
  height: 22px;
  border: 2px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.xt-kpi-bar__icon.metric-plant-output i {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  clip-path: polygon(50% 0, 92% 22%, 92% 72%, 50% 100%, 8% 72%, 8% 22%);
}

.xt-kpi-bar__icon.metric-plant-output::before {
  width: 2px;
  height: 20px;
  background: transparent;
  transform: rotate(30deg);
}

.xt-kpi-bar__icon.metric-finished-inbound i {
  width: 26px;
  height: 18px;
  border-radius: 4px;
  clip-path: polygon(0 38%, 50% 0, 100% 38%, 100% 100%, 0 100%);
}

.xt-kpi-bar__icon.metric-finished-inbound::before {
  width: 16px;
  height: 9px;
  border: 2px solid var(--xt-border);
  border-top: 0;
  transform: translateY(8px);
}

.xt-kpi-bar__icon.metric-process-throughput i {
  width: 28px;
  height: 24px;
  border-radius: 999px;
}

.xt-kpi-bar__icon.metric-process-throughput::before,
.xt-kpi-bar__icon.metric-process-throughput::after {
  width: 22px;
  height: 6px;
  border: 2px solid var(--xt-border);
  border-radius: 999px;
}

.xt-kpi-bar__icon.metric-process-throughput::before {
  transform: translateY(-10px);
}

.xt-kpi-bar__icon.metric-process-throughput::after {
  transform: translateY(10px);
}

.xt-kpi-bar__icon.metric-process-throughput i,
.xt-kpi-bar__icon.metric-energy-per-ton i {
  border-radius: 999px;
}

.xt-kpi-bar__icon.metric-yield-rate i {
  border-radius: 50%;
}

.xt-kpi-bar__icon.metric-yield-rate::before {
  width: 14px;
  height: 8px;
  border-right: 2px solid var(--xt-border);
  border-bottom: 2px solid var(--xt-border);
  transform: rotate(45deg);
}

.xt-kpi-bar__icon.metric-energy-cost i,
.xt-kpi-bar__icon.metric-contract-tonnage i {
  width: 20px;
  height: 26px;
  border-radius: 4px;
}

.xt-kpi-bar__icon.metric-contract-tonnage::before,
.xt-kpi-bar__icon.metric-contract-tonnage::after {
  left: 16px;
  width: 16px;
  height: 2px;
  background: transparent;
}

.xt-kpi-bar__icon.metric-contract-tonnage::before {
  top: 19px;
}

.xt-kpi-bar__icon.metric-contract-tonnage::after {
  top: 26px;
}

.xt-kpi-bar__icon.metric-energy-cost {
  border-color: var(--xt-border);
  background: transparent;
}

.xt-kpi-bar__icon.metric-energy-cost::before {
  content: '¥';
  color: var(--xt-text);

  font-size: 24px;
  font-weight: 600;
  line-height: 1;
}

.xt-kpi-bar__icon.metric-energy-cost i {
  display: none;
}

.xt-kpi-bar__label {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.xt-kpi-bar__delta {
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  padding: 1px 7px;
  background: transparent;
  color: var(--xt-text);
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.xt-kpi-bar__delta.tone-positive {
  color: var(--xt-success);
  background: transparent;
  border-color: var(--xt-border);
}

.xt-kpi-bar__delta.tone-negative {
  color: var(--xt-danger);
  background: transparent;
  border-color: var(--xt-border);
}

.xt-kpi-bar__value {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  gap: var(--xt-space-1);
  color: var(--xt-text);

  margin-top: 5px;
  font-size: clamp(21px, 2vw, 28px);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.xt-kpi-bar__value span {
  color: var(--xt-text);
}

.xt-kpi-bar__value small {
  color: var(--xt-text);

  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.xt-kpi-bar__source {
  position: relative;
  z-index: 1;
  margin-top: 2px;
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.xt-kpi-bar__card.tone-positive .xt-kpi-bar__value span {
  color: var(--xt-success);
}

.xt-kpi-bar__card.tone-negative .xt-kpi-bar__value span {
  color: var(--xt-danger);
}

.xt-kpi-bar__spark {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 24px;
  margin-top: 2px;
}

.xt-kpi-bar__hint {
  position: relative;
  z-index: 1;
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
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
    grid-template-columns: 38px minmax(0, 1fr);
  }

  .xt-kpi-bar__icon {
    width: 36px;
    height: 36px;
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
