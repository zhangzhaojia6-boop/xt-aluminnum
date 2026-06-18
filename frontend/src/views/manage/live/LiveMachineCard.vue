<template>
  <button class="live-machine-card" :class="`is-${machine.tone}`" type="button" @click="$emit('select', machine)">
    <span class="live-machine-card__status"><i></i>{{ statusText }}</span>
    <strong>{{ machine.machineName }}</strong>
    <em>{{ machine.sourceLabel ? `${machine.workshopName} · ${machine.sourceLabel}` : machine.workshopName }}</em>
    <div class="live-machine-card__metric">
      <span>下机量</span>
      <b data-xt-numeric>{{ outputText }} 吨</b>
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
</script>

<style scoped>
.live-machine-card {
  position: relative;
  min-height: 154px;
  overflow: hidden;
  text-align: left;
  color: inherit;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(5, 25, 48, 0.9), rgba(1, 12, 24, 0.94)),
    radial-gradient(circle at 30% 0%, rgba(0, 242, 255, 0.12), transparent 44%);
  padding: 12px;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
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
  border-color: rgba(0, 242, 255, 0.52);
  box-shadow: 0 8px 18px rgba(0, 29, 68, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.live-machine-card__status,
.live-machine-card strong,
.live-machine-card em,
.live-machine-card__metric,
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
  font-weight: 700;
}

.live-machine-card__status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentcolor 18%, transparent);
}

.live-machine-card strong {
  display: block;
  margin-top: 9px;
  color: rgba(225, 253, 255, 0.94);
  font-size: 17px;
  line-height: 1.16;
}

.live-machine-card em {
  display: block;
  margin-top: 4px;
  color: rgba(185, 223, 235, 0.62);
  font-style: normal;
  font-size: 12px;
}

.live-machine-card__metric {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 14px 0 11px;
  color: rgba(225, 253, 255, 0.86);
}

.live-machine-card__metric span {
  color: rgba(185, 223, 235, 0.58);
  font-size: 12px;
}

.live-machine-card__metric b {
  color: #e1fdff;
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 13px;
}

.live-machine-card__shifts {
  display: grid;
  gap: 5px;
  color: rgba(185, 223, 235, 0.72);
  font-size: 12px;
}

.live-machine-card__shifts span {
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.1);
  border-radius: 6px;
  background: rgba(0, 242, 255, 0.05);
  padding: 4px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-machine-card.is-success {
  color: #00f2ff;
  border-color: rgba(0, 242, 255, 0.28);
}

.live-machine-card.is-warning {
  color: #ffab00;
  border-color: rgba(255, 171, 0, 0.34);
}

.live-machine-card.is-danger {
  color: #ff5d4d;
  border-color: rgba(255, 93, 77, 0.42);
}

.live-machine-card.is-pending,
.live-machine-card.is-muted {
  color: #7aa2bd;
}

@media (prefers-reduced-motion: reduce) {
  .live-machine-card {
    transition: none;
  }
}
</style>
