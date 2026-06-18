<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <span class="xt-kpi-bar__icon" :class="`metric-${item.key}`" aria-hidden="true">
        <i />
      </span>
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
  grid-template-columns: 54px minmax(0, 1fr);
  gap: 11px;
  align-items: start;
  min-height: 98px;
  padding: 11px 12px;
  border: 1px solid rgba(70, 157, 238, 0.26);
  border-radius: 12px;
  background:
    radial-gradient(circle at 92% 86%, rgba(35, 130, 235, 0.2), transparent 46%),
    linear-gradient(180deg, rgba(18, 57, 88, 0.68), rgba(5, 24, 42, 0.94)),
    rgba(4, 21, 37, 0.94);
  box-shadow:
    inset 0 1px 0 rgba(189, 225, 255, 0.08),
    0 10px 24px rgba(0, 8, 16, 0.28);
  overflow: hidden;
}

.xt-kpi-bar__card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(52, 154, 255, 0.8), transparent);
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
  background: rgba(33, 137, 255, 0.14);
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
  border: 1px solid rgba(67, 158, 255, 0.34);
  border-radius: 14px;
  background:
    linear-gradient(145deg, rgba(40, 142, 255, 0.34), rgba(5, 31, 55, 0.9)),
    rgba(6, 34, 58, 0.92);
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
  border: 2px solid rgba(109, 193, 255, 0.9);
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(69, 164, 255, 0.72), rgba(7, 63, 112, 0.82));
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
  background: rgba(209, 238, 255, 0.62);
  transform: rotate(30deg);
}

.xt-kpi-bar__icon.metric-finished-inbound i {
  width: 26px;
  height: 18px;
  border-radius: 3px 3px 7px 7px;
  clip-path: polygon(0 38%, 50% 0, 100% 38%, 100% 100%, 0 100%);
}

.xt-kpi-bar__icon.metric-finished-inbound::before {
  width: 16px;
  height: 9px;
  border: 2px solid rgba(209, 238, 255, 0.64);
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
  border: 2px solid rgba(109, 193, 255, 0.72);
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
  border-right: 2px solid rgba(150, 239, 172, 0.9);
  border-bottom: 2px solid rgba(150, 239, 172, 0.9);
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
  background: rgba(209, 238, 255, 0.68);
}

.xt-kpi-bar__icon.metric-contract-tonnage::before {
  top: 19px;
}

.xt-kpi-bar__icon.metric-contract-tonnage::after {
  top: 26px;
}

.xt-kpi-bar__icon.metric-energy-cost {
  border-color: rgba(246, 174, 57, 0.44);
  background:
    linear-gradient(145deg, rgba(246, 174, 57, 0.24), rgba(5, 31, 55, 0.9)),
    rgba(6, 34, 58, 0.92);
}

.xt-kpi-bar__icon.metric-energy-cost::before {
  content: '¥';
  color: rgba(255, 202, 93, 0.94);
  font-family: var(--xt-font-number);
  font-size: 24px;
  font-weight: 950;
  line-height: 1;
}

.xt-kpi-bar__icon.metric-energy-cost i {
  display: none;
}

.xt-kpi-bar__label {
  color: rgba(226, 240, 255, 0.68);
  font-size: 12px;
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
  margin-top: 5px;
  font-size: clamp(21px, 2vw, 28px);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.xt-kpi-bar__value span {
  color: var(--xt-text-inverse);
}

.xt-kpi-bar__value small {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-family: var(--xt-font-body);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-kpi-bar__source {
  position: relative;
  z-index: 1;
  margin-top: 2px;
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
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
  height: 24px;
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
