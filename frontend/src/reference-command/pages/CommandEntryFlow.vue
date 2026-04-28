<template>
  <div class="xt-page command-entry-flow">
    <XtPageHeader title="填报流程页" eyebrow="04 ENTRY FLOW" />
    <XtGrid>
      <XtKpi label="当前步骤" value="2" unit="/6" trend="产量录入" />
      <XtKpi label="产量" value="285.60" unit="吨" trend="班次" />
      <XtKpi label="良率" value="98.5" unit="%" trend="自动估算" tone="success" />
    </XtGrid>
    <XtCard title="流程步骤">
      <ol class="flow-steps">
        <li v-for="step in steps" :key="step" :class="{ 'is-current': step === '产量录入' }">{{ step }}</li>
      </ol>
    </XtCard>
    <XtActionBar>
      <button type="button">上一步</button>
      <button type="button">保存草稿</button>
      <button type="button" class="is-primary">下一步</button>
    </XtActionBar>
  </div>
</template>

<script setup>
import { XtActionBar, XtCard, XtGrid, XtKpi, XtPageHeader } from '../../components/xt'

const steps = ['机台确认', '产量录入', '质量确认', '能耗录入', '异常说明', '提交']
</script>

<style scoped>
.command-entry-flow {
  display: grid;
  gap: var(--xt-space-5);
}

.flow-steps {
  display: grid;
  gap: var(--xt-space-3);
  margin: 0;
  padding-left: var(--xt-space-5);
}

.flow-steps li {
  color: var(--xt-text-secondary);
}

.flow-steps li.is-current {
  color: var(--xt-primary);
  font-weight: 700;
}

button {
  height: 36px;
  padding: 0 var(--xt-space-4);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
}

button.is-primary {
  border-color: var(--xt-primary);
  color: #fff;
  background: var(--xt-primary);
}
</style>
