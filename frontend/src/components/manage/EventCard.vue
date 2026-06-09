<template>
  <button
    type="button"
    class="xt-event-card"
    :class="{ 'is-fallback': event.isFallback }"
    @click="emit('open', event)"
  >
    <span class="xt-event-card__time">{{ timeLabel }}</span>
    <span class="xt-event-card__pill" :class="`pill-${event.domain}`">{{ domainLabel }}</span>
    <span class="xt-event-card__summary">
      <b>{{ event.summary }}</b>
      <small v-if="detailText">{{ detailText }}</small>
    </span>
    <span class="xt-event-card__arrow" aria-hidden="true">→</span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({ event: { type: Object, required: true } })
const emit = defineEmits(['open'])

const DOMAIN_LABELS = { production: '生产', quality: '质检', reconciliation: '对账', reporting: '填报', energy: '能耗', mes: 'MES' }
const domainLabel = computed(() => DOMAIN_LABELS[props.event.domain] || props.event.domain)
const detailText = computed(() => String(props.event.detail || '').trim())
const timeLabel = computed(() => {
  if (!props.event.occurredAt) return '--:--'
  return dayjs(props.event.occurredAt).format('HH:mm')
})
</script>

<style scoped>
.xt-event-card {
  display: grid;
  grid-template-columns: 60px 56px 1fr 24px;
  align-items: center;
  gap: var(--xt-space-2);
  width: 100%;
  min-height: 56px;
  padding: var(--xt-space-2) var(--xt-space-3);
  background: transparent;
  border: 0;
  text-align: left;
  color: inherit;
  cursor: pointer;
  transition: background-color var(--xt-motion-fast) var(--xt-ease), transform var(--xt-motion-fast) var(--xt-ease);
}
.xt-event-card:hover { background: var(--xt-bg-panel-soft); }
.xt-event-card:active { transform: scale(0.995); }
.xt-event-card.is-fallback {
  background: color-mix(in srgb, var(--xt-color-warning) 8%, var(--xt-bg-panel));
}
.xt-event-card__time { color: var(--xt-text-muted); font-variant-numeric: tabular-nums; font-size: var(--xt-text-sm); }
.xt-event-card__pill {
  justify-self: start;
  padding: 1px var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}
.pill-production { color: var(--xt-color-warning); background: color-mix(in srgb, var(--xt-color-warning) 12%, transparent); }
.pill-quality { color: var(--xt-color-danger); background: color-mix(in srgb, var(--xt-color-danger) 12%, transparent); }
.pill-reconciliation { color: var(--xt-color-accent); background: color-mix(in srgb, var(--xt-color-accent) 12%, transparent); }
.pill-reporting { color: var(--xt-text-muted); background: var(--xt-bg-panel-soft); }
.xt-event-card__summary {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  overflow: hidden;
}
.xt-event-card__summary b,
.xt-event-card__summary small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.xt-event-card__summary b {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 850;
}
.xt-event-card__summary small {
  margin-top: 2px;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 650;
}
.xt-event-card__arrow { color: var(--xt-text-muted); font-size: var(--xt-text-md); }
.pill-energy,
.pill-mes { color: var(--xt-color-warning); background: color-mix(in srgb, var(--xt-color-warning) 12%, transparent); }
@media (max-width: 720px) {
  .xt-event-card { grid-template-columns: 50px 56px 1fr 24px; min-height: 64px; }
}
</style>
