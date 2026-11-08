<template>
  <section class="xt-source-strip" :class="`tone-${strip.tone}`" data-testid="factory-source-strip">
    <span class="xt-source-strip__scan" aria-hidden="true"></span>
    <span class="xt-source-strip__rail" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </span>

    <div class="xt-source-strip__source">
      <span class="xt-source-strip__pulse" aria-hidden="true"></span>
      <div>
        <small>主数据</small>
        <strong>{{ strip.sourceLabel }}</strong>
      </div>
    </div>

    <ul class="xt-source-strip__items">
      <li v-for="item in strip.items" :key="item.key">
        <span class="xt-source-strip__label">{{ item.label }}</span>
        <span class="xt-source-strip__readout">
          <b>{{ item.value }}</b>
          <small>{{ item.unit }}</small>
        </span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import { buildFactorySourceStrip } from '../../utils/factorySourceStrip.js'

const props = defineProps({
  overview: { type: Object, default: () => ({}) },
})

const strip = computed(() => buildFactorySourceStrip(props.overview))
</script>

<style scoped>
.xt-source-strip {
  position: relative;
  display: grid;
  grid-template-columns: minmax(190px, 0.72fr) minmax(0, 2.6fr);
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;

  overflow: hidden;
}

.xt-source-strip::before,
.xt-source-strip::before, .xt-source-strip::after { display: none; }

.xt-source-strip::after {
  position: absolute;
  content: "";
  pointer-events: none;
}

.xt-source-strip::before {
  inset: 0 0 auto;
  height: 2px;
  background: transparent;
  opacity: 0.8;
}

.xt-source-strip::before, .xt-source-strip::after { display: none; }

.xt-source-strip::after {
  right: -34px;
  bottom: -42px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--xt-primary) 14%, transparent);
}

.xt-source-strip__scan {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 112px;
  background: transparent;
  opacity: 0.32;
  transform: translateX(24%);
  pointer-events: none;
}

.xt-source-strip__rail {
  position: absolute;
  inset: auto var(--xt-space-3) var(--xt-space-2);
  z-index: 1;
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 1fr;
  gap: var(--xt-space-1);
  pointer-events: none;
}

.xt-source-strip__rail span {
  height: 1px;
  border-radius: var(--xt-radius-pill);
  background: transparent;
  opacity: 0.38;
}

.xt-source-strip__source,
.xt-source-strip__items {
  position: relative;
  z-index: 2;
}

.xt-source-strip__source {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-width: 0;
  padding: var(--xt-space-2);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.xt-source-strip__source small,
.xt-source-strip__label {
  display: block;
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.xt-source-strip__source strong {
  display: block;
  margin-top: 2px;
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 600;
  line-height: 1.1;
}

.xt-source-strip__pulse {
  position: relative;
  width: 12px;
  height: 12px;
  flex: 0 0 auto;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);

}

.xt-source-strip__pulse::after {
  position: absolute;
  inset: -8px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  content: "";
}

.xt-source-strip.tone-success .xt-source-strip__pulse {
  background: transparent;

}

.xt-source-strip.tone-warning .xt-source-strip__pulse {
  background: transparent;

}

.xt-source-strip.tone-danger .xt-source-strip__pulse {
  background: transparent;

}

.xt-source-strip__items {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-source-strip__items li {
  min-width: 0;
  padding: var(--xt-space-2);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;

}

.xt-source-strip__readout {
  display: block;
  white-space: nowrap;
}

.xt-source-strip__items b {
  display: inline-block;
  margin-top: 5px;
  color: var(--xt-text);

  font-size: var(--xt-text-xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}

.xt-source-strip__items small {
  margin-left: 4px;
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

@media (max-width: 860px) {
  .xt-source-strip {
    grid-template-columns: 1fr;
  }

  .xt-source-strip__items {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .xt-source-strip {
    padding: var(--xt-space-2);
  }

  .xt-source-strip__items {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-source-strip__scan {
    transition: none;
  }
}
</style>
