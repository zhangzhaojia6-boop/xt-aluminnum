<template>
  <section class="review-command-deck" data-testid="review-command-deck">
    <article
      v-for="card in cards"
      :key="card.key"
      class="review-command-deck__card"
      :class="card.tone ? `is-${card.tone}` : ''"
      tabindex="0"
    >
      <div class="review-command-deck__head">
        <span class="review-command-deck__icon review-icon-badge" :class="iconToneClass(card.tone)">
          <el-icon>
            <component :is="toneIcon(card.tone)" />
          </el-icon>
        </span>
        <div class="review-command-deck__label">{{ card.label }}</div>
      </div>
      <strong>{{ card.value }}</strong>
    </article>
  </section>
</template>

<script setup>
import { CircleCheckFilled, CloseBold, DataAnalysis, WarningFilled } from '@element-plus/icons-vue'

defineProps({
  cards: {
    type: Array,
    default: () => []
  }
})

function toneIcon(tone) {
  if (tone === 'success') return CircleCheckFilled
  if (tone === 'alert') return WarningFilled
  if (tone === 'danger') return CloseBold
  return DataAnalysis
}

function iconToneClass(tone) {
  if (tone === 'success') return 'is-success'
  if (tone === 'alert') return 'is-warn'
  if (tone === 'danger') return 'is-danger'
  if (tone === 'primary') return 'is-primary'
  return 'is-neutral'
}
</script>

<style scoped>
.review-command-deck {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.review-command-deck__card {
  --deck-accent: rgba(148, 163, 184, 0.46);
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 8px;
  min-height: 86px;
  padding: 12px;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    background-color var(--app-motion-fast) ease;
}

.review-command-deck__card::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 2px;
  background: var(--deck-accent);
}

.review-command-deck__card:hover,
.review-command-deck__card:focus-visible {
  transform: translateY(-2px);
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-md);
  background: var(--xt-bg-panel-soft);
  outline: none;
}

.review-command-deck__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-command-deck__icon {
  flex: 0 0 auto;
}

.review-command-deck__card.is-alert {
  --deck-accent: rgba(217, 119, 6, 0.7);
}

.review-command-deck__card.is-danger {
  --deck-accent: rgba(220, 38, 38, 0.75);
}

.review-command-deck__card.is-success {
  --deck-accent: rgba(22, 163, 74, 0.72);
}

.review-command-deck__card.is-primary {
  --deck-accent: rgba(37, 99, 235, 0.72);
}

.review-command-deck__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--xt-text-secondary);
  line-height: 1.2;
}

.review-command-deck__card strong {
  font-size: clamp(20px, 1.6vw, 26px);
  line-height: 1.08;
  color: var(--app-text);
}

@media (max-width: 1220px) {
  .review-command-deck {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .review-command-deck {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .review-command-deck {
    grid-template-columns: 1fr;
  }

  .review-command-deck__card {
    min-height: auto;
  }
}
</style>
