<template>
  <button class="live-machine-card" :class="`is-${machine.tone}`" type="button" @click="$emit('select', machine)">
    <span class="live-machine-card__status"><i></i>{{ statusText }}</span>
    <strong>{{ machine.machineName }}</strong>
    <em>{{ machine.sourceLabel ? `${machine.workshopName} · ${machine.sourceLabel}` : machine.workshopName }}</em>
    <div class="live-machine-card__metrics">
      <span>
        <em>上机量</em>
        <b data-xt-numeric>{{ inputText }} 吨</b>
      </span>
      <span>
        <em>下机量</em>
        <b data-xt-numeric>{{ outputText }} 吨</b>
      </span>
    </div>
    <div class="live-machine-card__shifts">
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
  if (props.machine.tone === 'success') return '正常'
  if (props.machine.tone === 'warning') return '待核'
  if (props.machine.tone === 'danger') return '异常'
  if (props.machine.tone === 'pending') return '待归属'
  return '暂无'
})

const outputText = computed(() => formatNumber(props.machine.output, 2))
const inputText = computed(() => formatNumber(props.machine.input, 2))
</script>

<style scoped>
.live-machine-card {
  position: relative;
  min-height: 154px;
  overflow: hidden;
  text-align: left;
  color: inherit;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  padding: 12px;
  cursor: pointer;

  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.live-machine-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: currentcolor;
  opacity: 0.8;
  content: "";
}

.live-machine-card::after {
  position: absolute;
  right: -22px;
  top: -28px;
  width: 86px;
  height: 86px;
  border: 1px solid currentcolor;
  border-radius: 50%;
  opacity: 0.12;
  content: "";
}

.live-machine-card:hover {
  transform: translateY(-2px);
  border-color: var(--xt-border);

}

.live-machine-card__status,
.live-machine-card strong,
.live-machine-card em,
.live-machine-card__metrics,
.live-machine-card__shifts {
  position: relative;
  z-index: 1;
}

.live-machine-card__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: currentcolor;
  font-size: 12px;
  font-weight: 600;
}

.live-machine-card__status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;

}

.live-machine-card strong {
  display: block;
  margin-top: 9px;
  color: var(--xt-text);
  font-size: 17px;
  line-height: 1.16;
}

.live-machine-card em {
  display: block;
  margin-top: 4px;
  color: var(--xt-text-secondary);
  font-style: normal;
  font-size: 12px;
}

.live-machine-card__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 14px 0 11px;
  color: var(--xt-text);
}

.live-machine-card__metrics span {
  min-width: 0;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 7px;
  background: transparent;
}

.live-machine-card__metrics em {
  display: block;
  color: var(--xt-text-secondary);
  font-style: normal;
  font-size: 12px;
}

.live-machine-card__metrics b {
  display: block;
  overflow: hidden;
  margin-top: 4px;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-card__shifts {
  display: grid;
  gap: 5px;
  color: var(--xt-text);
  font-size: 12px;
}

.live-machine-card__shifts span {
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  padding: 4px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-card.is-success {
  color: var(--xt-primary);
  border-color: var(--xt-border);
}

.live-machine-card.is-warning {
  color: var(--xt-warning);
  border-color: var(--xt-border);
}

.live-machine-card.is-danger {
  color: var(--xt-text);
  border-color: var(--xt-border);
}

.live-machine-card.is-pending,
.live-machine-card.is-muted {
  color: var(--xt-text);
}

@media (prefers-reduced-motion: reduce) {
  .live-machine-card {
    transition: none;
  }
}
</style>
