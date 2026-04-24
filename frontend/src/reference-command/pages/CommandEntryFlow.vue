<template>
  <div class="cmd-page cmd-entry-flow-page" data-module="04">
    <section class="cmd-entry-flow">
      <img class="cmd-entry-flow__visual" :src="entryFlowImage" alt="" />
      <div class="cmd-entry-flow__functional">
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
        <label v-for="row in formRows" :key="row.name">
          <span>{{ row.name }}</span>
          <input :value="row.value" readonly />
        </label>
        <button type="button">上一步</button>
        <button type="button">保存草稿</button>
        <button type="button">下一步</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import entryFlowImage from '../assets/entry-flow.png'

const steps = ['基础信息', '产量录入', '能耗辅项', '异常补充', '图片上传', '提交成功']
const formRows = [
  { name: '产线', value: 'A00 铝线', rate: '已选', state: '正常' },
  { name: '产量', value: '285.60', rate: '吨', state: '待提交' },
  { name: '良率', value: '98.5%', rate: '自动', state: '正常' }
]
</script>
