<template>
  <section class="live-metric-compare" aria-label="算法与填报对照">
    <header class="live-section-head">
      <div>
        <span>口径对照</span>
        <strong>算法优先</strong>
      </div>
      <em>填报保留对照</em>
    </header>
    <div class="live-metric-compare__grid">
      <article v-for="item in items" :key="item.label" :class="`is-${item.tone}`">
        <span>{{ item.label }}</span>
        <strong data-xt-numeric>{{ item.primaryValue }}</strong>
        <div>
          <b>{{ item.primaryLabel }}</b>
          <em>{{ item.compareLabel }} {{ item.compareValue }}</em>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.live-metric-compare {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.17);
  border-radius: 18px;
  padding: 16px;
  background:
    linear-gradient(180deg, rgba(9, 36, 64, 0.82), rgba(3, 15, 29, 0.92)),
    radial-gradient(circle at 78% 0%, rgba(0, 242, 255, 0.14), transparent 44%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.live-metric-compare::before {
  position: absolute;
  inset: auto 18px 18px auto;
  width: 160px;
  height: 160px;
  border: 1px solid rgba(0, 242, 255, 0.13);
  border-radius: 50%;
  opacity: 0.72;
  content: "";
}

.live-section-head,
.live-metric-compare__grid {
  position: relative;
  z-index: 1;
}

.live-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.live-section-head span {
  color: rgba(116, 245, 255, 0.72);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.live-section-head strong {
  display: block;
  margin-top: 3px;
  color: rgba(225, 253, 255, 0.94);
  font-size: 19px;
}

.live-section-head em {
  color: #ffab00;
  font-style: normal;
  font-size: 12px;
}

.live-metric-compare__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.live-metric-compare__grid article {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 12px;
  background: rgba(2, 16, 31, 0.72);
  padding: 14px;
}

.live-metric-compare__grid article::before {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent, rgba(0, 242, 255, 0.11), transparent);
  transform: translateX(-115%);
  content: "";
  animation: liveCompareSweep 5.4s linear infinite;
}

.live-metric-compare__grid article > span,
.live-metric-compare__grid article > strong,
.live-metric-compare__grid article > div {
  position: relative;
  z-index: 1;
}

.live-metric-compare__grid article > span {
  color: rgba(185, 223, 235, 0.64);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.live-metric-compare__grid article > strong {
  display: block;
  margin: 9px 0;
  color: #e1fdff;
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: clamp(24px, 2.5vw, 34px);
  line-height: 1;
  letter-spacing: -0.05em;
  text-shadow: 0 0 18px rgba(0, 242, 255, 0.24);
}

.live-metric-compare__grid div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.live-metric-compare__grid b,
.live-metric-compare__grid em {
  font-size: 12px;
  font-style: normal;
}

.live-metric-compare__grid b {
  color: rgba(225, 253, 255, 0.82);
}

.live-metric-compare__grid em {
  color: rgba(185, 223, 235, 0.62);
}

.live-metric-compare__grid article.is-warning > strong {
  color: #ffe1a3;
}

.live-metric-compare__grid article.is-danger > strong {
  color: #ffd2cc;
}

.live-metric-compare__grid article.is-success > strong {
  color: #e1fdff;
}

@keyframes liveCompareSweep {
  0% { transform: translateX(-115%); }
  50%, 100% { transform: translateX(115%); }
}

@media (max-width: 1180px) {
  .live-metric-compare__grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-metric-compare__grid article::before {
    animation: none;
  }
}
</style>
