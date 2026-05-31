<template>
  <el-drawer :model-value="open" direction="rtl" size="520px" class="live-machine-drawer" @close="$emit('close')">
    <template #header>
      <div class="live-machine-drawer__head">
        <span>{{ machine?.workshopName || '机列' }}</span>
        <strong>{{ machine?.machineName || '未选择' }}</strong>
      </div>
    </template>

    <section v-if="machine" class="live-machine-drawer__body">
      <div class="live-machine-drawer__stats">
        <span><b data-xt-numeric>{{ formatNumber(machine.input, 2) }}</b><em>投入 吨</em></span>
        <span><b data-xt-numeric>{{ formatNumber(machine.output, 2) }}</b><em>产出 吨</em></span>
        <span><b data-xt-numeric>{{ formatNumber(machine.scrap, 2) }}</b><em>废料 吨</em></span>
      </div>

      <div class="live-machine-drawer__shifts">
        <article v-for="shift in machine.shifts" :key="`${shift.shiftId}-${shift.shiftName}`">
          <strong>{{ shift.shiftName }}</strong>
          <span>{{ shift.statusText }}</span>
          <em data-xt-numeric>{{ formatNumber(shift.output, 2) }} 吨</em>
        </article>
      </div>

      <div v-if="detailLoading" class="live-machine-drawer__loading">正在读取明细</div>
      <div v-else-if="detailError" class="live-machine-drawer__error">{{ detailError }}</div>
      <el-table v-else :data="detailRows" size="small" max-height="260" empty-text="暂无填报明细">
        <el-table-column prop="entry_status" label="状态" width="88" />
        <el-table-column prop="tracking_card_no" label="随行卡" min-width="120" />
        <el-table-column prop="responsible_name" label="责任人" min-width="110" />
        <el-table-column prop="output_weight" label="产出" width="96" align="right" />
      </el-table>
    </section>
  </el-drawer>
</template>

<script setup>
import { formatNumber } from '../../../utils/display.js'

defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  machine: {
    type: Object,
    default: null,
  },
  detailRows: {
    type: Array,
    default: () => [],
  },
  detailLoading: {
    type: Boolean,
    default: false,
  },
  detailError: {
    type: String,
    default: '',
  },
})

defineEmits(['close'])
</script>

<style scoped>
:deep(.live-machine-drawer) {
  background:
    linear-gradient(180deg, rgba(5, 24, 46, 0.98), rgba(2, 12, 25, 0.98)),
    radial-gradient(circle at 15% 0%, rgba(0, 242, 255, 0.16), transparent 44%);
  color: rgba(225, 253, 255, 0.94);
}

:deep(.live-machine-drawer .el-drawer__header) {
  margin-bottom: 0;
  border-bottom: 1px solid rgba(0, 242, 255, 0.14);
  padding: 18px 20px;
  color: rgba(225, 253, 255, 0.94);
}

:deep(.live-machine-drawer .el-drawer__body) {
  padding: 18px 20px 22px;
}

.live-machine-drawer__head span,
.live-machine-drawer__head strong {
  display: block;
}

.live-machine-drawer__head span {
  color: rgba(116, 245, 255, 0.72);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.live-machine-drawer__head strong {
  margin-top: 4px;
  color: rgba(225, 253, 255, 0.94);
  font-size: 22px;
}

.live-machine-drawer__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.live-machine-drawer__stats span,
.live-machine-drawer__shifts article {
  border: 1px solid rgba(0, 242, 255, 0.15);
  border-radius: 10px;
  padding: 12px;
  background:
    linear-gradient(180deg, rgba(6, 28, 52, 0.8), rgba(2, 15, 29, 0.88)),
    radial-gradient(circle at 0% 0%, rgba(0, 242, 255, 0.1), transparent 45%);
}

.live-machine-drawer__stats b,
.live-machine-drawer__stats em {
  display: block;
}

.live-machine-drawer__stats b {
  color: #e1fdff;
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: 24px;
  line-height: 1;
  text-shadow: 0 0 16px rgba(0, 242, 255, 0.24);
}

.live-machine-drawer__stats em {
  margin-top: 6px;
  color: rgba(185, 223, 235, 0.64);
  font-style: normal;
  font-size: 12px;
}

.live-machine-drawer__shifts {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.live-machine-drawer__shifts article {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 10px;
  align-items: center;
}

.live-machine-drawer__shifts strong {
  color: rgba(225, 253, 255, 0.9);
}

.live-machine-drawer__shifts span {
  color: #74f5ff;
  font-size: 12px;
}

.live-machine-drawer__shifts em {
  color: rgba(225, 253, 255, 0.88);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-style: normal;
}

.live-machine-drawer__loading {
  color: #ffab00;
  margin-bottom: 12px;
}

.live-machine-drawer__error {
  color: #ff5d4d;
  margin-bottom: 12px;
}

:deep(.live-machine-drawer .el-table) {
  --el-table-bg-color: rgba(1, 16, 31, 0.82);
  --el-table-tr-bg-color: rgba(1, 16, 31, 0.82);
  --el-table-header-bg-color: rgba(7, 38, 66, 0.88);
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-border-color: rgba(0, 242, 255, 0.12);
  --el-table-text-color: rgba(225, 253, 255, 0.86);
  --el-table-header-text-color: rgba(116, 245, 255, 0.82);
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 10px;
  overflow: hidden;
}

@media (max-width: 560px) {
  .live-machine-drawer__stats {
    grid-template-columns: 1fr;
  }

  .live-machine-drawer__shifts article {
    grid-template-columns: 1fr;
  }
}
</style>
