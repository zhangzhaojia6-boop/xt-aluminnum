<template>
  <button class="live-machine-card" :class="`is-${machine.tone}`" type="button" @click="$emit('select', machine)">
    <span class="live-machine-card__status">{{ statusText }}</span>
    <strong>{{ machine.machineName }}</strong>
    <em>{{ machine.workshopName }}</em>
    <div class="live-machine-card__metric">
      <span>产出</span>
      <b data-xt-numeric>{{ machine.output.toFixed(2) }} 吨</b>
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
</script>
