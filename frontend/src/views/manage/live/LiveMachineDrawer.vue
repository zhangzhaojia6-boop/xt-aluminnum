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
        <span><b data-xt-numeric>{{ formatNumber(machine.input, 2) }}</b><em>上机量 吨</em></span>
        <span><b data-xt-numeric>{{ formatNumber(machine.output, 2) }}</b><em>下机量 吨</em></span>
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
        <el-table-column prop="input_weight" label="上机量" width="96" align="right" />
        <el-table-column prop="output_weight" label="下机量" width="96" align="right" />
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
  background: transparent;
  color: var(--xt-text);
}

:deep(.live-machine-drawer .el-drawer__header) {
  margin-bottom: 0;
  border-bottom: 1px solid var(--xt-border);
  padding: 18px 20px;
  color: var(--xt-text);
}

:deep(.live-machine-drawer .el-drawer__body) {
  padding: 18px 20px 22px;
}

.live-machine-drawer__head span,
.live-machine-drawer__head strong {
  display: block;
}

.live-machine-drawer__head span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.live-machine-drawer__head strong {
  margin-top: 4px;
  color: var(--xt-text);
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
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 12px;
  background: transparent;
}

.live-machine-drawer__stats b,
.live-machine-drawer__stats em {
  display: block;
}

.live-machine-drawer__stats b {
  color: var(--xt-text);

  font-size: 24px;
  line-height: 1;
}

.live-machine-drawer__stats em {
  margin-top: 6px;
  color: var(--xt-text-secondary);
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
  color: var(--xt-text);
}

.live-machine-drawer__shifts span {
  color: var(--xt-text);
  font-size: 12px;
}

.live-machine-drawer__shifts em {
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-style: normal;
}

.live-machine-drawer__loading {
  color: var(--xt-warning);
  margin-bottom: 12px;
}

.live-machine-drawer__error {
  color: var(--xt-text);
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
  border: 1px solid var(--xt-border);
  border-radius: 4px;
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
