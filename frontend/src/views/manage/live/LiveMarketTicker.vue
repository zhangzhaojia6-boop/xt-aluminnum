<template>
  <section class="live-market-ticker" aria-label="实时行情">
    <article
      v-for="item in items"
      :key="item.label"
      class="live-market-ticker__item"
      :class="`is-${item.tone}`"
    >
      <span>{{ item.label }}</span>
      <strong data-xt-numeric><AnimatedMetricValue :value="item.value" /></strong>
      <em>{{ item.source }}</em>
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
  grid-template-columns: repeat(8, minmax(132px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: thin;
}

.live-market-ticker__item {
  position: relative;
  min-width: 132px;
  min-height: 96px;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.17);
  border-radius: 8px;
  padding: 13px 14px;
  background:
    linear-gradient(180deg, rgba(11, 41, 72, 0.82), rgba(3, 18, 34, 0.9)),
    radial-gradient(circle at 18% 0%, rgba(0, 242, 255, 0.16), transparent 50%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 8px 18px rgba(0, 29, 68, 0.16);
}

.live-market-ticker__item::before {
  position: absolute;
  top: 0;
  right: 12px;
  left: 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.2), transparent);
  content: "";
}

.live-market-ticker__item::after {
  position: absolute;
  right: 12px;
  bottom: 11px;
  width: 34px;
  height: 3px;
  border-radius: 999px;
  background: currentcolor;
  opacity: 0.34;
  content: "";
}

.live-market-ticker__item span,
.live-market-ticker__item strong,
.live-market-ticker__item em {
  position: relative;
  z-index: 1;
}

.live-market-ticker__item span {
  display: block;
  color: rgba(185, 223, 235, 0.68);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.live-market-ticker__item strong {
  display: block;
  margin-top: 8px;
  color: #e1fdff;
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: clamp(24px, 2vw, 32px);
  line-height: 1;
  letter-spacing: -0.05em;
  font-variant-numeric: tabular-nums;
  transition: color 160ms ease, opacity 160ms ease;
}

.live-market-ticker__item em {
  display: block;
  margin-top: 9px;
  color: rgba(185, 223, 235, 0.55);
  font-style: normal;
  font-size: 11px;
}

.live-market-ticker__item.is-success { color: #00f2ff; }
.live-market-ticker__item.is-warning { color: #ffab00; }
.live-market-ticker__item.is-danger { color: #ff5d4d; }
.live-market-ticker__item.is-muted { color: #7aa2bd; }

.live-market-ticker__item.is-success strong { color: #e1fdff; }
.live-market-ticker__item.is-warning strong { color: #ffe1a3; }
.live-market-ticker__item.is-danger strong { color: #ffd2cc; }

@media (max-width: 1180px) {
  .live-market-ticker {
    grid-template-columns: repeat(4, minmax(140px, 1fr));
  }
}

@media (max-width: 720px) {
  .live-market-ticker {
    grid-template-columns: repeat(2, minmax(136px, 1fr));
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-market-ticker__item strong {
    transition: none;
  }
}

</style>
