<template>
  <section class="live-machine-matrix" aria-label="全厂机列矩阵">
    <header class="live-section-head">
      <div>
        <span>全厂机列矩阵</span>
        <strong>{{ matrix.machineCount }} 台机列</strong>
      </div>
      <em>{{ matrix.pendingMachines.length }} 台待归属</em>
    </header>

    <div v-if="loading" class="live-machine-matrix__skeleton">
      <i v-for="index in 12" :key="index"></i>
    </div>

    <div v-else-if="matrix.workshops.length" class="live-machine-matrix__workshops">
      <article v-for="workshop in matrix.workshops" :key="workshop.workshopId || workshop.workshopName" class="live-machine-workshop">
        <div class="live-machine-workshop__head">
          <strong>{{ workshop.workshopName }}</strong>
          <span data-xt-numeric>{{ workshop.output.toFixed(2) }} 吨</span>
        </div>
        <div class="live-machine-workshop__grid">
          <LiveMachineCard
            v-for="machine in workshop.machines"
            :key="machine.id"
            :machine="machine"
            @select="$emit('select', $event)"
          />
        </div>
      </article>
    </div>

    <div v-else class="live-machine-matrix__empty">暂无机列数据</div>

    <aside v-if="matrix.pendingMachines.length" class="live-machine-matrix__pending" aria-label="待归属">
      <strong>待归属</strong>
      <button
        v-for="machine in matrix.pendingMachines"
        :key="machine.id"
        type="button"
        @click="$emit('select', machine)"
      >
        <span>{{ machine.workshopName }}</span>
        <b>{{ machine.machineName }}</b>
        <em data-xt-numeric>{{ machine.output.toFixed(2) }} 吨</em>
      </button>
    </aside>
  </section>
</template>

<script setup>
import LiveMachineCard from './LiveMachineCard.vue'

defineProps({
  matrix: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['select'])
</script>
