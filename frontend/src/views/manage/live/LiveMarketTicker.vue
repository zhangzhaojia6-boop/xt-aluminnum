<template>
  <section class="live-market-ticker" aria-label="实时行情">
    <article
      v-for="item in items"
      :key="item.label"
      class="live-market-ticker__item"
      :class="`is-${item.tone}`"
    >
      <span class="live-market-ticker__label">
        <i aria-hidden="true" />
        {{ item.label }}
      </span>
      <strong data-xt-numeric aria-live="polite"><AnimatedMetricValue :value="item.value" /></strong>
      <em>来源 {{ item.source }}</em>
    </article>
  </section>
</template>

<script setup>
import AnimatedMetricValue from './AnimatedMetricValue.vue'

defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.live-market-ticker {
  display: grid;
  grid-template-columns: repeat(4, minmax(178px, 1fr));
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 3px;
  scrollbar-width: thin;
}

.live-market-ticker__item {
  position: relative;
  min-width: 178px;
  min-height: 118px;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 15px 16px;
  background: transparent;

  transform: translateY(0);
  transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
}

.live-market-ticker__item::before {
  position: absolute;
  top: 0;
  right: 14px;
  left: 14px;
  height: 2px;
  background: transparent;
  content: "";
}

.live-market-ticker__item::after {
  position: absolute;
  right: 14px;
  bottom: 13px;
  width: 48px;
  height: 4px;
  border-radius: 999px;
  background: currentcolor;
  opacity: 0.38;
  content: "";
  transform: scaleX(0.82);
  transform-origin: right center;
  transition: transform 220ms ease, opacity 220ms ease;
}

.live-market-ticker__item:hover {
  border-color: var(--xt-border);
  transform: translateY(-1px);
}

.live-market-ticker__item:hover::after,
.live-market-ticker__item:focus-within::after {
  opacity: 0.62;
  transform: scaleX(1);
}

.live-market-ticker__label,
.live-market-ticker__item strong,
.live-market-ticker__item em {
  position: relative;
  z-index: 1;
}

.live-market-ticker__label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--xt-text);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.live-market-ticker__label i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentcolor;

  transition: transform 180ms ease;
}

.live-market-ticker__item:hover .live-market-ticker__label i {
  transform: scale(1.16);
}

.live-market-ticker__item strong {
  display: block;
  margin-top: 11px;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: clamp(32px, 3.2vw, 52px);
  line-height: 0.96;
  letter-spacing: -0.08em;
  font-variant-numeric: tabular-nums;
  transition: color 160ms ease, opacity 160ms ease, transform 160ms ease;
}

.live-market-ticker__item em {
  display: block;
  margin-top: 12px;
  color: var(--xt-text-secondary);
  font-style: normal;
  font-size: 12px;
  letter-spacing: 0.04em;
}

.live-market-ticker__item.is-success { color: var(--xt-primary); }
.live-market-ticker__item.is-warning { color: var(--xt-warning); }
.live-market-ticker__item.is-danger { color: var(--xt-text); }
.live-market-ticker__item.is-muted { color: var(--xt-text); }

.live-market-ticker__item.is-success strong { color: var(--xt-text); }
.live-market-ticker__item.is-warning strong { color: var(--xt-text); }
.live-market-ticker__item.is-danger strong { color: var(--xt-text); }

@media (max-width: 1180px) {
  .live-market-ticker {
    grid-template-columns: repeat(2, minmax(172px, 1fr));
  }
}

@media (max-width: 720px) {
  .live-market-ticker {
    grid-template-columns: repeat(2, minmax(148px, 1fr));
  }

  .live-market-ticker__item {
    min-width: 148px;
    min-height: 108px;
  }

  .live-market-ticker__item strong {
    font-size: clamp(28px, 8vw, 38px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-market-ticker__item,
  .live-market-ticker__item::after,
  .live-market-ticker__label i,
  .live-market-ticker__item strong {
    transition: none;
  }
}

</style>
