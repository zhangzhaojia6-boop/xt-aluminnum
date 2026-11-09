<template>
  <button class="live-machine-card" :class="machine.unreported ? 'is-unreported' : `is-${machine.tone}`" type="button" @click="$emit('select', machine)">
    <span class="live-machine-card__status"><i></i>{{ statusText }}</span>
    <strong>{{ machine.machineName }}</strong>
    <em>{{ machine.sourceLabel ? `${machine.workshopName} · ${machine.sourceLabel}` : machine.workshopName }}</em>
    <div class="live-machine-card__metrics">
      <span>
        <em>上机量</em>
        <b data-xt-numeric>{{ inputText }}</b>
      </span>
      <span>
        <em>下机量</em>
        <b data-xt-numeric>{{ outputText }}</b>
      </span>
    </div>
    <div v-if="hasSubmittedShift" class="live-machine-card__shifts">
      <span v-for="shift in machine.shifts.slice(0, 3)" :key="`${shift.shiftId}-${shift.shiftName}`">
        {{ shift.shiftName }} {{ shift.statusText }}
      </span>
    </div>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber } from '../../../utils/display.js'

const props = defineProps({
  machine: {
    type: Object,
    required: true,
  },
})

defineEmits(['select'])

const statusText = computed(() => {
  if (props.machine.unreported) return '暂无'
  if (props.machine.tone === 'success') return '正常'
  if (props.machine.tone === 'warning') return '待核'
  if (props.machine.tone === 'danger') return '异常'
  if (props.machine.tone === 'pending') return '待归属'
  return '暂无'
})

const hasSubmittedShift = computed(() => props.machine.shifts.some((shift) => (
  !['not_started', 'not_applicable'].includes(shift.status)
)))

const outputText = computed(() => (props.machine.unreported ? '—' : `${formatNumber(props.machine.output, 2)} 吨`))
const inputText = computed(() => (props.machine.unreported ? '—' : `${formatNumber(props.machine.input, 2)} 吨`))
</script>

<style scoped>
.live-machine-card {
  display: grid;
  align-content: start;
  gap: var(--xt-space-1);
  min-width: 0;
  padding: var(--xt-space-3);
  border: 0;
  border-top: 2px solid var(--xt-border);
  background: transparent;
  color: var(--xt-text-secondary);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .live-machine-card:hover {
    background: color-mix(in srgb, var(--xt-primary) 5%, transparent);
  }
}

.live-machine-card__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: currentcolor;
  font-size: var(--xt-text-xs);
  font-weight: 500;
}

.live-machine-card__status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;
}

.live-machine-card strong {
  color: var(--xt-text);
  font-size: var(--xt-text-base);
  font-weight: 600;
}

.live-machine-card em {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-style: normal;
}

.live-machine-card__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-2);
  margin-top: var(--xt-space-1);
}

.live-machine-card__metrics span {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.live-machine-card__metrics b {
  overflow: hidden;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-card__shifts {
  display: grid;
  gap: 2px;
  margin-top: var(--xt-space-1);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.live-machine-card__shifts span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-card.is-success {
  border-top-color: var(--xt-primary);
  color: var(--xt-primary);
}

.live-machine-card.is-warning {
  border-top-color: var(--xt-warning);
  color: var(--xt-warning);
}

.live-machine-card.is-danger {
  border-top-color: var(--xt-danger);
  color: var(--xt-danger);
}

.live-machine-card.is-unreported {
  border-top-color: var(--xt-border);
  color: var(--xt-text-muted);
}

@media (prefers-reduced-motion: reduce) {
  .live-machine-card {
    transition: none;
  }
}
</style>
