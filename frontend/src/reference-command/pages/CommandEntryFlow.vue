<template>
  <CenterPageShell no="04" title="填报流程页" data-module="04">
    <template #tools>
      <StatusBadge label="草稿自动保存" tone="normal" />
      <SourceBadge source="operator" />
    </template>

    <MockDataNotice source="fallback" message="流程示例使用兜底字段，正式提交仍进入真实填报表单。" />

    <SectionCard title="填报步骤">
      <div class="cmd-step-row">
        <span v-for="(step, index) in steps" :key="step" class="cmd-step" :class="{ 'is-active': index === 1 }">
          {{ index + 1 }} {{ step }}
        </span>
      </div>
    </SectionCard>

    <div class="center-grid-2">
      <SectionCard title="基础信息">
        <DataTableShell :columns="formColumns" :rows="formRows">
          <template #cell-state="{ value }">
            <StatusBadge :label="value" :tone="value === '待提交' ? 'warning' : 'success'" />
          </template>
        </DataTableShell>
      </SectionCard>

      <SectionCard title="操作">
        <div class="action-grid">
          <ActionTile label="上一步" meta="返回基础信息" />
          <ActionTile label="保存草稿" meta="暂存当前字段" />
          <ActionTile label="下一步" meta="进入确认提交" primary />
        </div>
      </SectionCard>
    </div>
  </CenterPageShell>
</template>

<script setup>
import ActionTile from '../../components/app/ActionTile.vue'
import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'

const steps = ['基础信息', '产量录入', '能耗辅项', '异常补充', '图片上传', '提交成功']
const formColumns = [
  { key: 'name', label: '字段' },
  { key: 'value', label: '数值' },
  { key: 'rate', label: '口径' },
  { key: 'state', label: '状态' }
]
const formRows = [
  { id: 'line', name: '产线', value: 'A00 铝线', rate: '已选', state: '正常' },
  { id: 'output', name: '产量', value: '285.60', rate: '吨', state: '待提交' },
  { id: 'yield', name: '良率', value: '98.5%', rate: '自动', state: '正常' }
]
</script>
