<template>
  <section class="live-machine-matrix" aria-label="全厂机列矩阵">
    <header class="live-section-head">
      <div>
        <span>全厂机列矩阵</span>
        <strong>{{ matrix.machineCount }} 台机列</strong>
      </div>
      <div class="live-machine-matrix__tools">
        <em>{{ matrix.pendingMachines.length }} 台待归属</em>
        <div class="live-machine-matrix__legend" aria-hidden="true">
          <span class="is-success">正常</span>
          <span class="is-warning">待核</span>
          <span class="is-danger">异常</span>
        </div>
      </div>
    </header>

    <div v-if="loading" class="live-machine-matrix__skeleton">
      <i v-for="index in 12" :key="index"></i>
    </div>

    <div v-else-if="matrix.workshops.length" class="live-machine-matrix__workshops">
      <article v-for="workshop in matrix.workshops" :key="workshop.workshopId || workshop.workshopName" class="live-machine-workshop">
        <div class="live-machine-workshop__head">
          <strong>{{ workshop.workshopName }}</strong>
          <div class="live-machine-workshop__totals">
            <span data-xt-numeric>上机 {{ formatNumber(workshop.input, 2) }} 吨</span>
            <span data-xt-numeric>下机 {{ formatNumber(workshop.output, 2) }} 吨</span>
          </div>
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
        <em data-xt-numeric>上机 {{ formatNumber(machine.input, 2) }} 吨 / 下机 {{ formatNumber(machine.output, 2) }} 吨</em>
      </button>
    </aside>
  </section>
</template>

<script setup>
import LiveMachineCard from './LiveMachineCard.vue'
import { formatNumber } from '../../../utils/display.js'

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

<style scoped>
.live-machine-matrix {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.17);
  border-radius: 18px;
  padding: 16px;
  background:
    linear-gradient(180deg, rgba(10, 35, 62, 0.78), rgba(4, 17, 33, 0.9)),
    radial-gradient(circle at 50% -10%, rgba(0, 242, 255, 0.16), transparent 42%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.live-machine-matrix::before {
  position: absolute;
  inset: 0;
  opacity: 0.24;
  background:
    linear-gradient(rgba(0, 242, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.06) 1px, transparent 1px);
  background-size: 28px 28px;
  content: "";
  pointer-events: none;
}

.live-section-head,
.live-machine-matrix__workshops,
.live-machine-matrix__skeleton,
.live-machine-matrix__empty,
.live-machine-matrix__pending {
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

.live-machine-matrix__tools {
  display: grid;
  gap: 8px;
  justify-items: end;
}

.live-machine-matrix__tools em {
  color: #ffab00;
  font-style: normal;
  font-size: 12px;
}

.live-machine-matrix__legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.live-machine-matrix__legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 999px;
  padding: 3px 8px;
  background: rgba(2, 16, 31, 0.72);
  color: rgba(185, 223, 235, 0.72);
  font-size: 11px;
  letter-spacing: 0;
}

.live-machine-matrix__legend span::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentcolor 16%, transparent);
  content: "";
}

.live-machine-matrix__legend .is-success { color: #00f2ff; }
.live-machine-matrix__legend .is-warning { color: #ffab00; }
.live-machine-matrix__legend .is-danger { color: #ff5d4d; }

.live-machine-matrix__workshops {
  display: grid;
  gap: 12px;
}

.live-machine-workshop {
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 14px;
  padding: 12px;
  background:
    linear-gradient(180deg, rgba(6, 27, 50, 0.84), rgba(3, 15, 28, 0.84)),
    radial-gradient(circle at 0% 0%, rgba(0, 242, 255, 0.12), transparent 40%);
}

.live-machine-workshop__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  color: rgba(225, 253, 255, 0.9);
}

.live-machine-workshop__head strong {
  font-size: 15px;
}

.live-machine-workshop__totals {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.live-machine-workshop__totals span {
  color: #74f5ff;
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  transition: color 160ms ease, opacity 160ms ease;
}

.live-machine-workshop__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 10px;
}

.live-machine-matrix__pending {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(0, 242, 255, 0.14);
}

.live-machine-matrix__pending > strong {
  grid-column: 1 / -1;
  color: #ffab00;
}

.live-machine-matrix__pending button {
  display: grid;
  gap: 4px;
  text-align: left;
  color: inherit;
  border: 1px solid rgba(255, 171, 0, 0.24);
  border-radius: 10px;
  background: rgba(25, 20, 7, 0.42);
  padding: 11px;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.live-machine-matrix__pending button:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 171, 0, 0.54);
  box-shadow: 0 8px 18px rgba(0, 29, 68, 0.16);
}

.live-machine-matrix__pending b,
.live-machine-matrix__pending em {
  color: rgba(225, 253, 255, 0.9);
  font-style: normal;
}

.live-machine-matrix__pending em {
  font-variant-numeric: tabular-nums;
  transition: color 160ms ease, opacity 160ms ease;
}

.live-machine-matrix__pending span {
  color: rgba(185, 223, 235, 0.62);
  font-size: 12px;
}

.live-machine-matrix__skeleton {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 10px;
}

.live-machine-matrix__skeleton i {
  height: 128px;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.06), rgba(0, 242, 255, 0.18), rgba(0, 242, 255, 0.06));
}

.live-machine-matrix__empty {
  display: grid;
  min-height: 220px;
  place-items: center;
  color: rgba(185, 223, 235, 0.7);
}

@media (max-width: 720px) {
  .live-section-head {
    flex-direction: column;
  }

  .live-machine-matrix__tools {
    justify-items: start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-machine-matrix__pending button {
    transition: none;
  }

  .live-machine-workshop__totals span,
  .live-machine-matrix__pending em {
    transition: none;
  }
}
</style>
