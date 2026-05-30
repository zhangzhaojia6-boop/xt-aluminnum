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
        <span><b data-xt-numeric>{{ machine.input?.toFixed?.(2) || '0.00' }}</b><em>投入 吨</em></span>
        <span><b data-xt-numeric>{{ machine.output?.toFixed?.(2) || '0.00' }}</b><em>产出 吨</em></span>
        <span><b data-xt-numeric>{{ machine.scrap?.toFixed?.(2) || '0.00' }}</b><em>废料 吨</em></span>
      </div>

      <div class="live-machine-drawer__shifts">
        <article v-for="shift in machine.shifts" :key="`${shift.shiftId}-${shift.shiftName}`">
          <strong>{{ shift.shiftName }}</strong>
          <span>{{ shift.statusText }}</span>
          <em data-xt-numeric>{{ shift.output.toFixed(2) }} 吨</em>
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
.live-machine-drawer__head span,
.live-machine-drawer__head strong {
  display: block;
}

.live-machine-drawer__head span {
  color: rgba(178, 202, 232, 0.7);
}

.live-machine-drawer__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.live-machine-drawer__stats span,
.live-machine-drawer__shifts article {
  border: 1px solid rgba(148, 196, 255, 0.16);
  border-radius: 14px;
  padding: 12px;
  background: rgba(4, 14, 28, 0.56);
}

.live-machine-drawer__stats b,
.live-machine-drawer__stats em {
  display: block;
}

.live-machine-drawer__stats b {
  color: #f0b84a;
}

.live-machine-drawer__stats em {
  color: rgba(178, 202, 232, 0.68);
  font-style: normal;
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

.live-machine-drawer__loading {
  color: #f0b84a;
  margin-bottom: 12px;
}

.live-machine-drawer__error {
  color: #ff6b78;
  margin-bottom: 12px;
}
</style>
