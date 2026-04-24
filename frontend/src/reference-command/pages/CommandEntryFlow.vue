<template>
  <div class="cmd-page cmd-module-page" data-module="04">
    <header class="cmd-module-page__head">
      <div class="cmd-module-page__title">
        <span class="cmd-module-page__number">04</span>
        <h1>填报流程页</h1>
      </div>
      <span class="cmd-status">草稿自动保存</span>
    </header>
    <div class="cmd-step-row">
      <span v-for="(step, index) in steps" :key="step" class="cmd-step" :class="{ 'is-active': index === 1 }">
        {{ index + 1 }} {{ step }}
      </span>
    </div>
    <div class="cmd-module-page__kpis">
      <CommandKpi v-for="kpi in viewModel.kpis" :key="kpi.label" v-bind="kpi" />
    </div>
    <div class="cmd-module-page__body">
      <main class="cmd-module-page__primary">
        <CommandTable :rows="formRows" />
      </main>
      <aside class="cmd-module-page__side">
        <CommandTrend :values="viewModel.trend" />
        <CommandTable :rows="viewModel.tableRows" />
      </aside>
    </div>
    <CommandActionBar :actions="viewModel.actions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

import CommandActionBar from '../components/CommandActionBar.vue'
import CommandKpi from '../components/CommandKpi.vue'
import CommandTable from '../components/CommandTable.vue'
import CommandTrend from '../components/CommandTrend.vue'
import { adaptEntryFlow } from '../data/moduleAdapters.js'

const steps = ['基础信息', '产量录入', '能耗辅项', '异常补充', '图片上传', '提交成功']
const viewModel = computed(() => adaptEntryFlow())
const formRows = [
  { name: '产线', value: 'A00 铝线', rate: '已选', state: '正常' },
  { name: '产量', value: '285.60', rate: '吨', state: '待提交' },
  { name: '良率', value: '98.5%', rate: '自动', state: '正常' }
]
</script>
